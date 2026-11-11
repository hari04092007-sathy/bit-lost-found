from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    department = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    role = "student"
    def get_id(self): return f"u:{self.id}"

class Admin(UserMixin, db.Model):
    __tablename__ = "admins"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    role = "admin"
    def get_id(self): return f"a:{self.id}"

class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)

class Item(db.Model):
    __tablename__ = "items"
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), nullable=False)          # lost | found
    name = db.Column(db.String(120), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(120), nullable=False)
    event_date = db.Column(db.Date, nullable=False)
    photo = db.Column(db.String(120))
    contact = db.Column(db.String(150))                      # private
    extra = db.Column(db.Text)                               # private
    status = db.Column(db.String(12), default="pending", nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.relationship("Category")
    reporter = db.relationship("User")
    claims = db.relationship("Claim", backref="item", cascade="all, delete-orphan")

class Claim(db.Model):
    __tablename__ = "claims"
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    claimant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    details = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(10), default="pending", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    claimant = db.relationship("User")
