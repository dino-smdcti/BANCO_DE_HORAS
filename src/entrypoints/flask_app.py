import os
import sys
import json
import urllib.error
import urllib.request

from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, render_template, request
from flask_login import LoginManager, UserMixin, current_user
from flask_wtf import CSRFProtect
from itsdangerous import URLSafeTimedSerializer
import smtplib
from sqlalchemy import create_engine

from src.adapters.orm import start_mappers
from src.entrypoints import admin_routes, auth_routes, employee_routes, manager_routes, work_routes
from src.service_layer import services
from src.service_layer.absence_processor import process_daily_absences
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork, resolve_database_url
from scripts.run_migrations import run_all_migrations
from src.config import (
        ADMIN_ROLES,
        BREVO_API_TIMEOUT_SECONDS,
        BREVO_API_URL,
        DATE_FORMAT,
        DEFAULT_SMTP_PORT,
        DEFAULT_SMTP_SERVER,
        EMAIL_FROM_NAME,
        FALLBACK_ANALYSIS_DATE,
        MANAGEMENT_ROLES,
        MAX_NOTIFICATIONS_DISPLAYED,
        MINUTES_PER_HOUR,
        ROLE_ADMIN,
        ROLE_EMPLOYEE,
        ROLE_GESTOR,
        ROLE_LABELS,
        ROLE_MANAGER,
        SMTP_SSL_PORT,
        SMTP_TIMEOUT_SECONDS,
        WORKFORCE_ENABLED,
)

load_dotenv()


def _resolve_secret_key(environ):
        """Return a usable SECRET_KEY, refusing a weak dev key in production.

        A explicit value always wins; otherwise a clearly-labeled insecure key is
        used for development/testing, but production (FLASK_ENV=production or
        VERCEL) fails fast when SECRET_KEY is missing.
        """
        secret = environ.get("SECRET_KEY")
        is_production = environ.get("FLASK_ENV") == "production" or bool(environ.get("VERCEL"))
        if not secret and is_production:
                raise RuntimeError("SECRET_KEY must be set via the SECRET_KEY environment variable in production.")
        return secret or "dev-only-insecure-secret-key"


app = Flask(__name__, template_folder="templates")
app.config["SECRET_KEY"] = _resolve_secret_key(os.environ)
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", DEFAULT_SMTP_SERVER)
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", DEFAULT_SMTP_PORT))
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

csrf = CSRFProtect(app)


def _database_url():
        return resolve_database_url()


app.config["SQLALCHEMY_DATABASE_URI"] = _database_url()

_engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])

try:
        start_mappers()
except Exception:
        pass

run_all_migrations(_engine)

try:
        with SqlAlchemyUnitOfWork() as init_uow:
                services.seed_holidays(init_uow)
except Exception as error:
        print(f"Error seeding holidays on startup: {error}", file=sys.stderr)

serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])


@login_manager.user_loader
def flask_load_user(user_id):
        return load_user(user_id)


class AuthenticatedUser(UserMixin):
        def __init__(self, user):
                self.id = user.user_id
                self.email = user.email
                self.role = user.role
                self.full_name = user.profile.full_name
                self.is_profile_complete = user.is_profile_complete
                self.work_schedule = user.work_schedule
                self.has_schedule = user.work_schedule is not None


def load_user(user_id):
        """Load a user for Flask-Login, normalizing role casing when needed."""
        with SqlAlchemyUnitOfWork() as uow:
                return _authenticated_or_repair(uow, user_id)


def _authenticated_or_repair(uow, user_id):
        user = _fetch_user(uow, user_id)
        if user and user.is_active:
                return AuthenticatedUser(user)
        if _repair_role_casing(uow, user_id):
                return _authenticated_after_repair(uow, user_id)
        return None


def _authenticated_after_repair(uow, user_id):
        user = _fetch_user(uow, user_id)
        if user and user.is_active:
                return AuthenticatedUser(user)
        return None


def _fetch_user(uow, user_id):
        try:
                return uow.users.get_user_by_id(int(user_id))
        except (LookupError, ValueError, TypeError):
                return None


def _repair_role_casing(uow, user_id):
        """Normalize a stored role to lowercase when it breaks the enum mapping."""
        try:
                with uow.session.begin():
                        return _repair_in_session(uow, user_id)
        except (LookupError, ValueError, TypeError):
                return False
        return False


def _repair_in_session(uow, user_id):
        raw_user = uow.session.execute("SELECT * FROM users WHERE id = :uid", {"uid": int(user_id)}).first()
        if raw_user and hasattr(raw_user, "role"):
                uow.session.execute("UPDATE users SET role = :role WHERE id = :uid", {"role": raw_user.role.lower(), "uid": int(user_id)})
                uow.session.commit()
                return True
        return False


@app.before_request
def run_daily_absences_check():
        if request.endpoint and not request.endpoint.startswith("static"):
                _run_absence_check()


def _run_absence_check():
        uow = SqlAlchemyUnitOfWork()
        try:
                process_daily_absences(uow)
        except Exception as error:
                print(f"Error running daily absences check: {error}", file=sys.stderr)


@app.context_processor
def utility_processor():
        def get_role_label(role_value, user_email=None):
                if role_value == ROLE_MANAGER and user_email == "nagelalima1307.smdcti@gmail.com":
                        return "Gestor"
                return ROLE_LABELS.get(role_value, role_value)
        return dict(
                get_role_label=get_role_label,
                ROLE_ADMIN=ROLE_ADMIN,
                ROLE_EMPLOYEE=ROLE_EMPLOYEE,
                ROLE_GESTOR=ROLE_GESTOR,
                ROLE_MANAGER=ROLE_MANAGER,
                ADMIN_ROLES=ADMIN_ROLES,
                MANAGEMENT_ROLES=MANAGEMENT_ROLES,
                MINUTES_PER_HOUR=MINUTES_PER_HOUR,
                FALLBACK_ANALYSIS_DATE=FALLBACK_ANALYSIS_DATE,
                DATE_FORMAT=DATE_FORMAT,
                WORKFORCE_ENABLED=WORKFORCE_ENABLED,
                data_app_mode="work" if request.path.startswith("/work") else "clock",
        )


@app.context_processor
def inject_notifications():
        if not current_user.is_authenticated:
                return {"user_notifs": [], "user_notifs_count": 0}
        uow = SqlAlchemyUnitOfWork()
        with uow:
                user = _load_authenticated_user(uow)
                if user:
                        notifs = [
                                {"message": n.message, "is_read": n.is_read, "created_at": n.created_at}
                                for n in user.notifications[:MAX_NOTIFICATIONS_DISPLAYED]
                        ]
                        return {"user_notifs": notifs, "user_notifs_count": user.unread_notifications_count}
        return {"user_notifs": [], "user_notifs_count": 0}


def _load_authenticated_user(uow):
        try:
                return uow.users.get_user_by_id(int(current_user.id))
        except (ValueError, TypeError):
                return None


def send_email(to_email, subject, body_html):
        """Deliver an email, trying SMTP first and falling back to the Brevo
        transactional API. Returns True if either channel delivered, else False.
        Failures are logged generically (never the recipient or raw error)."""
        if _send_smtp(to_email, subject, body_html):
                return True
        if _send_brevo(to_email, subject, body_html):
                return True
        print("Email send failed (SMTP and Brevo).", file=sys.stderr)
        return False


def _send_smtp(to_email, subject, body_html):
        """Send via SMTP; returns True on success, False on failure/misconfig."""
        if not app.config.get("MAIL_USERNAME") or not app.config.get("MAIL_PASSWORD"):
                return False

        msg = MIMEMultipart()
        msg["From"] = f"{EMAIL_FROM_NAME} <{app.config['MAIL_USERNAME']}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html"))

        try:
                server = _smtp_connect()
                server.login(app.config["MAIL_USERNAME"], app.config["MAIL_PASSWORD"])
                server.send_message(msg)
                try:
                        server.quit()
                except Exception:
                        pass
                return True
        except Exception:
                print("SMTP send failed.", file=sys.stderr)
                return False


def _send_brevo(to_email, subject, body_html):
        """Send via the Brevo transactional email API (fallback when SMTP fails)."""
        api_key = os.environ.get("BREVO_API_KEY")
        if not api_key:
                return False
        sender_email = app.config.get("MAIL_USERNAME")
        if not sender_email:
                return False

        payload = {
                "sender": {"name": EMAIL_FROM_NAME, "email": sender_email},
                "to": [{"email": to_email}],
                "subject": subject,
                "htmlContent": body_html,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
                BREVO_API_URL,
                data=data,
                headers={
                        "api-key": api_key,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                },
                method="POST",
        )
        try:
                with urllib.request.urlopen(req, timeout=BREVO_API_TIMEOUT_SECONDS) as resp:
                        if 200 <= resp.status < 300:
                                return True
                        print("Brevo API returned an error status.", file=sys.stderr)
                        return False
        except Exception:
                print("Brevo API send failed.", file=sys.stderr)
                return False



def send_email_with_fallback(to_email, subject, body_html):
        """Send an email; on failure render a secure HTML fallback page for
        management users so a blocked reset/invite link stays usable. Returns
        None when no fallback applies (caller keeps its default flow)."""
        if send_email(to_email, subject, body_html):
                return None
        if current_user.is_authenticated and current_user.role in MANAGEMENT_ROLES:
                return render_template(
                        "email_fallback.html",
                        subject=subject,
                        recipient=to_email,
                        content=body_html,
                )
        return None


def _smtp_connect():
        port = app.config["MAIL_PORT"]
        server_host = app.config["MAIL_SERVER"]
        if port == SMTP_SSL_PORT:
                return smtplib.SMTP_SSL(server_host, port, timeout=SMTP_TIMEOUT_SECONDS)
        server = smtplib.SMTP(server_host, port, timeout=SMTP_TIMEOUT_SECONDS)
        server.ehlo()
        server.starttls()
        server.ehlo()
        return server


for _register in (auth_routes.register_routes, employee_routes.register_routes, manager_routes.register_routes, admin_routes.register_routes, work_routes.register_routes):
        _register(app)
