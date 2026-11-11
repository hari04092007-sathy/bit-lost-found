import os, re, smtplib, uuid
from datetime import date, datetime
from email.message import EmailMessage
from email.utils import parseaddr
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Admin, Category, Item, Claim
from matching import find_matches

load_dotenv()
BASE = os.path.dirname(os.path.abspath(__file__))
DOMAIN = "bitsathy.ac.in"
LOCATIONS = ["Main Library", "Admin Block", "Canteen", "Seminar Hall", "Sports Ground", "Hostel Block", "CSE Block", "ECE Block", "Mechanical Block", "Parking Area", "Bus Stand"]
DEPARTMENTS = ["CSE", "IT", "AI & DS", "ECE", "EEE", "Mechanical", "Civil", "Biotechnology", "MBA", "Other"]
ERR_DOMAIN = "Please register using your official BIT email ID."

app = Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get("SECRET_KEY") or os.urandom(24).hex(),
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///dev.db"),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024, UPLOAD_DIR=os.path.join(BASE, "static", "uploads"),
    SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
db.init_app(app)
ser = URLSafeTimedSerializer(app.config["SECRET_KEY"])
lm = LoginManager(app); lm.login_view = "login"; lm.login_message = "Please log in to continue."

@lm.user_loader
def load_user(uid):
    kind, _, i = (uid or "").partition(":")
    return db.session.get(User if kind == "u" else Admin, int(i)) if i.isdigit() and kind in "ua" else None

# ---------- CSRF ----------
import secrets
from flask import session
@app.before_request
def csrf_guard():
    session.setdefault("_csrf", secrets.token_hex(16))
    if request.method == "POST" and not secrets.compare_digest(request.form.get("_csrf", ""), session["_csrf"]): abort(400)
app.jinja_env.globals["csrf"] = lambda: session.get("_csrf", "")

# ---------- helpers ----------
def clean_email(raw):
    """Lower-case, parse, and require the exact domain @bitsathy.ac.in."""
    e = parseaddr(raw or "")[1].strip().lower()
    if not re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+", e): return None
    return e if e.rsplit("@", 1)[1] == DOMAIN else None

def send_mail(to, subject, body):
    host = os.environ.get("MAIL_SERVER")
    if not host:
        print(f"\n[DEV MAIL - no SMTP configured] To: {to}\n{subject}\n{body}\n"); return False
    m = EmailMessage(); m["To"], m["Subject"], m["From"] = to, subject, os.environ.get("MAIL_SENDER", "BIT Lost & Found")
    m.set_content(body)
    with smtplib.SMTP(host, int(os.environ.get("MAIL_PORT", 587)), timeout=15) as s:
        s.starttls(); s.login(os.environ["MAIL_USERNAME"], os.environ["MAIL_PASSWORD"]); s.send_message(m)
    return True

def send_verification(u):
    link = url_for("verify", token=ser.dumps(u.email, salt="verify"), _external=True)
    send_mail(u.email, "Verify your BIT Lost & Found account", f"Hello {u.name},\n\nConfirm your BIT email by opening this link (valid 24 hours):\n{link}\n")

def student_required(f):
    @wraps(f)
    @login_required
    def w(*a, **k):
        if current_user.role != "student" or not current_user.email_verified: abort(403)
        return f(*a, **k)
    return w

def admin_required(f):
    @wraps(f)
    @login_required
    def w(*a, **k):
        if current_user.role != "admin": abort(403)
        return f(*a, **k)
    return w

def save_photo(f):
    if not f or not f.filename: return None
    ext = secure_filename(f.filename).rsplit(".", 1)[-1].lower()
    if ext not in {"png", "jpg", "jpeg", "webp"}: raise ValueError("Photo must be PNG, JPG or WEBP.")
    head = f.read(12); f.seek(0)
    if not (head[:8] == b"\x89PNG\r\n\x1a\n" or head[:3] == b"\xff\xd8\xff" or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")):
        raise ValueError("File content is not a valid image.")
    name = f"{uuid.uuid4().hex}.{ext}"; f.save(os.path.join(app.config["UPLOAD_DIR"], name)); return name

def can_see_private(item):
    if not current_user.is_authenticated: return False
    if current_user.role == "admin" or item.reporter_id == current_user.id: return True
    return any(c.claimant_id == current_user.id and c.status == "approved" for c in item.claims)

app.jinja_env.globals.update(can_see_private=can_see_private, LOCATIONS=LOCATIONS)

# ---------- public ----------
@app.route("/")
def index():
    recent = Item.query.filter(Item.status.in_(["approved", "recovered"])).order_by(Item.created_at.desc()).limit(6).all()
    stats = dict(total=Item.query.filter(Item.status != "rejected").count(), recovered=Item.query.filter_by(status="recovered").count(),
                 pending=Claim.query.filter_by(status="pending").count())
    cats = [(c, Item.query.filter_by(category_id=c.id, status="approved").count()) for c in Category.query.order_by(Category.name)]
    return render_template("index.html", recent=recent, stats=stats, cats=cats)

@app.route("/browse")
def browse():
    a = request.args; q = Item.query.filter(Item.status.in_(["approved", "recovered"]))
    if a.get("q"):
        like = f"%{a['q'].strip()[:60]}%"; q = q.filter(db.or_(Item.name.ilike(like), Item.description.ilike(like)))
    if a.get("kind") in ("lost", "found"): q = q.filter_by(kind=a["kind"])
    if a.get("category", "").isdigit(): q = q.filter_by(category_id=int(a["category"]))
    if a.get("location") in LOCATIONS: q = q.filter_by(location=a["location"])
    if a.get("status") in ("approved", "recovered"): q = q.filter_by(status=a["status"])
    for key, op in (("from", lambda d: Item.event_date >= d), ("to", lambda d: Item.event_date <= d)):
        try: q = q.filter(op(date.fromisoformat(a[key])))
        except (KeyError, ValueError): pass
    return render_template("browse.html", items=q.order_by(Item.created_at.desc()).all(), cats=Category.query.order_by(Category.name).all(), a=a)

@app.route("/about")
def about(): return render_template("about.html")

@app.route("/item/<int:i>")
def item(i):
    it = db.session.get(Item, i) or abort(404)
    if it.status in ("pending", "rejected") and not (current_user.is_authenticated and (current_user.role == "admin" or it.reporter_id == current_user.id)): abort(404)
    matches = find_matches(it, Item.query.filter_by(status="approved").all()) if it.status == "approved" else []
    mine = current_user.is_authenticated and current_user.role == "student" and Claim.query.filter_by(item_id=i, claimant_id=current_user.id).first()
    return render_template("item.html", it=it, matches=matches, mine=mine)

# ---------- auth ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form; email = clean_email(f.get("email")); name = f.get("name", "").strip()
        try: year = int(f.get("year", 0))
        except ValueError: year = 0
        err = (ERR_DOMAIN if not email else "Enter your full name." if len(name) < 3 or len(name) > 100 else "Choose your department." if f.get("department") not in DEPARTMENTS
               else "Year of study must be 1 to 4." if year not in (1, 2, 3, 4) else "Password must be at least 8 characters, with letters and numbers." if not re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d).{8,128}", f.get("password", ""))
               else "Passwords do not match." if f.get("password") != f.get("confirm") else "An account with this email already exists." if User.query.filter_by(email=email).first() else None)
        if err: flash(err, "error"); return render_template("register.html", f=f, depts=DEPARTMENTS)
        u = User(name=name, email=email, department=f["department"], year=year, password_hash=generate_password_hash(f["password"]))
        db.session.add(u); db.session.commit()
        try: sent = send_verification(u)
        except Exception: sent = False; app.logger.exception("mail failed")
        flash("Account created. We sent a verification link to your BIT email." if sent else "Account created, but the email could not be sent. Use 'Resend verification' on the login page.", "info")
        return redirect(url_for("login"))
    return render_template("register.html", f={}, depts=DEPARTMENTS)

@app.route("/verify/<token>")
def verify(token):
    try: email = ser.loads(token, salt="verify", max_age=86400)
    except SignatureExpired: flash("This link has expired. Request a new one below.", "error"); return redirect(url_for("login"))
    except BadSignature: abort(404)
    u = User.query.filter_by(email=email).first_or_404(); u.email_verified = True; db.session.commit()
    flash("Email verified. You can log in now.", "info"); return redirect(url_for("login"))

@app.route("/resend", methods=["POST"])
def resend():
    u = User.query.filter_by(email=clean_email(request.form.get("email")) or "-").first()
    if u and not u.email_verified:
        try: send_verification(u)
        except Exception: app.logger.exception("mail failed")
    flash("If that BIT account exists and is unverified, a new link has been sent.", "info"); return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = clean_email(request.form.get("email"))
        if not email: flash(ERR_DOMAIN, "error"); return render_template("login.html")
        u = User.query.filter_by(email=email).first()
        if not u or not check_password_hash(u.password_hash, request.form.get("password", "")): flash("Invalid email ID or password.", "error"); return render_template("login.html")
        if not u.email_verified: flash("Please verify your BIT email before logging in.", "error"); return render_template("login.html", unverified=email)
        login_user(u); return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = clean_email(request.form.get("email"))
        if not email: flash(ERR_DOMAIN, "error"); return render_template("forgot.html")
        u = User.query.filter_by(email=email, email_verified=True).first()
        if u:
            link = url_for("reset", token=ser.dumps({"id": u.id, "h": u.password_hash[-12:]}, salt="reset"), _external=True)
            try: send_mail(u.email, "Reset your BIT Lost & Found password", f"Reset your password (valid 1 hour, single use):\n{link}\n")
            except Exception: app.logger.exception("mail failed")
        flash("If that account exists, a reset link has been sent.", "info"); return redirect(url_for("login"))
    return render_template("forgot.html")

@app.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    try: d = ser.loads(token, salt="reset", max_age=3600)
    except (BadSignature, SignatureExpired): flash("This reset link is invalid or has expired.", "error"); return redirect(url_for("forgot"))
    u = db.session.get(User, d["id"])
    if not u or u.password_hash[-12:] != d["h"]: flash("This reset link was already used.", "error"); return redirect(url_for("forgot"))
    if request.method == "POST":
        p = request.form.get("password", "")
        if not re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d).{8,128}", p) or p != request.form.get("confirm"): flash("Use 8+ characters with letters and numbers; both fields must match.", "error")
        else: u.password_hash = generate_password_hash(p); db.session.commit(); flash("Password updated. Log in with your new password.", "info"); return redirect(url_for("login"))
    return render_template("reset.html")

@app.route("/logout", methods=["POST"])
@login_required
def logout(): logout_user(); return redirect(url_for("index"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        a = Admin.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
        if a and check_password_hash(a.password_hash, request.form.get("password", "")): login_user(a); return redirect(url_for("admin"))
        flash("Invalid email ID or password.", "error")
    return render_template("login.html", admin=True)

# ---------- student ----------
@app.route("/report/<kind>", methods=["GET", "POST"])
@student_required
def report(kind):
    if kind not in ("lost", "found"): abort(404)
    cats = Category.query.order_by(Category.name).all()
    if request.method == "POST":
        f = request.form
        try:
            d = date.fromisoformat(f.get("date", ""))
            if d > date.today(): raise ValueError("The date cannot be in the future.")
            cat = db.session.get(Category, int(f.get("category", 0))) or (_ for _ in ()).throw(ValueError("Choose a category."))
            name, desc = f.get("name", "").strip(), f.get("description", "").strip()
            if not 3 <= len(name) <= 120 or not 10 <= len(desc) <= 2000: raise ValueError("Item name needs 3+ characters and the description 10+.")
            if f.get("location") not in LOCATIONS: raise ValueError("Choose a campus location.")
            photo = save_photo(request.files.get("photo"))
        except ValueError as e:
            flash(str(e) if str(e) and "invalid literal" not in str(e) and "Invalid isoformat" not in str(e) else "Check the date and category.", "error"); return render_template("report.html", kind=kind, cats=cats, f=f)
        db.session.add(Item(kind=kind, name=name, category_id=cat.id, description=desc, location=f["location"], event_date=d, photo=photo,
                            contact=f.get("contact", "").strip()[:150] or current_user.email, extra=f.get("extra", "").strip()[:1000], reporter_id=current_user.id))
        db.session.commit(); flash("Report submitted. It will appear publicly once an admin approves it.", "info"); return redirect(url_for("dashboard"))
    return render_template("report.html", kind=kind, cats=cats, f={}, now=date.today().isoformat())

@app.route("/dashboard")
@student_required
def dashboard():
    mine = Item.query.filter_by(reporter_id=current_user.id).order_by(Item.created_at.desc()).all()
    suggestions = {i.id: find_matches(i, Item.query.filter_by(status="approved").all(), 3) for i in mine if i.status == "approved"}
    return render_template("dashboard.html", mine=mine, suggestions=suggestions, claims=Claim.query.filter_by(claimant_id=current_user.id).all())

@app.route("/claim/<int:i>", methods=["POST"])
@student_required
def claim(i):
    it = db.session.get(Item, i) or abort(404)
    details = request.form.get("details", "").strip()
    if it.status != "approved" or it.reporter_id == current_user.id: abort(403)
    if len(details) < 15: flash("Describe something only the owner would know (15+ characters).", "error")
    elif Claim.query.filter_by(item_id=i, claimant_id=current_user.id).first(): flash("You have already submitted a claim for this item.", "error")
    else: db.session.add(Claim(item_id=i, claimant_id=current_user.id, details=details[:1500])); db.session.commit(); flash("Claim submitted. The reporter or an admin will review it.", "info")
    return redirect(url_for("item", i=i))

@app.route("/claim/<int:c>/<action>", methods=["POST"])
@login_required
def decide(c, action):
    cl = db.session.get(Claim, c) or abort(404)
    if action not in ("approve", "reject") or cl.status != "pending": abort(400)
    if not (current_user.role == "admin" or (current_user.role == "student" and cl.item.reporter_id == current_user.id)): abort(403)
    if action == "approve":
        cl.status = "approved"; cl.item.status = "recovered"
        for o in cl.item.claims:
            if o.id != cl.id and o.status == "pending": o.status = "rejected"
    else: cl.status = "rejected"
    db.session.commit(); flash(f"Claim {cl.status}.", "info")
    return redirect(request.referrer or url_for("dashboard"))

# ---------- admin ----------
@app.route("/admin")
@admin_required
def admin():
    s = {k: Item.query.filter_by(status=k).count() for k in ("pending", "approved", "recovered", "rejected")}
    s.update(users=User.query.count(), claims=Claim.query.filter_by(status="pending").count())
    return render_template("admin.html", items=Item.query.order_by(Item.status == "pending", Item.created_at.desc()).all(), claims=Claim.query.filter_by(status="pending").all(), s=s)

@app.route("/admin/item/<int:i>/<action>", methods=["POST"])
@admin_required
def admin_item(i, action):
    it = db.session.get(Item, i) or abort(404)
    if action == "delete": db.session.delete(it)
    elif action in ("approved", "rejected", "recovered"): it.status = action
    else: abort(400)
    db.session.commit(); return redirect(url_for("admin"))

@app.errorhandler(403)
def forbidden(e): return render_template("error.html", msg="You do not have access to this page. Student pages need a verified BIT account."), 403
@app.errorhandler(404)
def missing(e): return render_template("error.html", msg="That page does not exist."), 404
@app.errorhandler(413)
def big(e): return render_template("error.html", msg="Upload is too large (2 MB maximum)."), 413

@app.cli.command("init-db")
def init_db():
    db.create_all()
    for n in ["ID Cards", "Electronics", "Books & Notes", "Bags", "Keys", "Wallets", "Clothing", "Stationery", "Other"]:
        if not Category.query.filter_by(name=n).first(): db.session.add(Category(name=n))
    db.session.commit(); print("Database ready.")

@app.cli.command("create-admin")
def create_admin():
    import getpass
    e, n = input("Admin email: ").strip().lower(), input("Name: ").strip()
    db.session.add(Admin(email=e, name=n, password_hash=generate_password_hash(getpass.getpass("Password: ")))); db.session.commit(); print("Admin created.")

if __name__ == "__main__": app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
