# BIT Lost & Found
Student-built Lost & Found portal for Bannari Amman Institute of Technology (not officially endorsed). Flask + SQLAlchemy + MySQL.

## Run in VS Code
1. `python -m venv venv` then activate it (`venv\Scripts\activate` on Windows, `source venv/bin/activate` on macOS/Linux).
2. `pip install -r requirements.txt`
3. Create the MySQL database: `mysql -u root -p < schema.sql` (or skip and run step 5, which creates tables).
4. Copy `.env.example` to `.env` and fill in `SECRET_KEY`, `DATABASE_URL` and SMTP settings.
5. `flask --app app init-db`, then `flask --app app create-admin`.
6. `flask --app app run`, open http://127.0.0.1:5000. Admin login: /admin/login.

## Email verification
Real verification needs SMTP credentials in `.env` (for Gmail, use an app password). With no `MAIL_SERVER`, links are printed in the terminal for local development only; accounts are still unverified until the link is opened.

## Not done
Automated tests, CSRF is a lightweight session-token check (not Flask-WTF), no rate limiting, no seed demo data, no per-user email resend throttling, and none of it has been run against MySQL or a real SMTP server.
