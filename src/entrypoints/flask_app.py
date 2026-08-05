import os
import sys

from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, request
from flask_login import LoginManager, UserMixin, current_user
from itsdangerous import URLSafeTimedSerializer
import smtplib
from sqlalchemy import create_engine

from src.adapters.orm import start_mappers, metadata
from src.entrypoints import admin_routes, auth_routes, employee_routes, manager_routes
from src.service_layer import services
from src.service_layer.absence_processor import process_daily_absences
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork

load_dotenv()

app = Flask(__name__, template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


def _database_url():
        database_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
        if not database_url:
                if os.environ.get("VERCEL"):
                        return "sqlite:////tmp/banco_de_horas.db"
                return "sqlite:///banco_de_horas.db"
        if database_url.startswith("postgres://"):
                return database_url.replace("postgres://", "postgresql://", 1)
        return database_url


app.config["SQLALCHEMY_DATABASE_URI"] = _database_url()

_engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])

try:
        start_mappers()
except Exception:
        pass

metadata.create_all(_engine)

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
        if user:
                return AuthenticatedUser(user)
        if _repair_role_casing(uow, user_id):
                return _authenticated_after_repair(uow, user_id)
        return None


def _authenticated_after_repair(uow, user_id):
        user = _fetch_user(uow, user_id)
        if user:
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
                if role_value == "manager" and user_email == "nagelalima1307.smdcti@gmail.com":
                        return "Gestor"
                mapping = {
                        "employee": "Funcionário",
                        "manager": "Diretor",
                        "admin": "Secretário",
                }
                return mapping.get(role_value, role_value)
        return dict(get_role_label=get_role_label)


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
                                for n in user.notifications[:20]
                        ]
                        return {"user_notifs": notifs, "user_notifs_count": user.unread_notifications_count}
        return {"user_notifs": [], "user_notifs_count": 0}


def _load_authenticated_user(uow):
        try:
                return uow.users.get_user_by_id(int(current_user.id))
        except (ValueError, TypeError):
                return None


def send_email(to_email, subject, body_html):
        if not app.config.get("MAIL_USERNAME") or not app.config.get("MAIL_PASSWORD"):
                print("SMTP Error: MAIL_USERNAME or MAIL_PASSWORD not configured.", file=sys.stderr)
                return False

        msg = MIMEMultipart()
        msg["From"] = f"Banco de Horas <{app.config['MAIL_USERNAME']}>"
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
        except Exception as error:
                print(f"Detailed SMTP Error for {to_email}: {str(error)}", file=sys.stderr)
                return False


def _smtp_connect():
        port = app.config["MAIL_PORT"]
        server_host = app.config["MAIL_SERVER"]
        if port == 465:
                return smtplib.SMTP_SSL(server_host, port, timeout=8)
        server = smtplib.SMTP(server_host, port, timeout=8)
        server.ehlo()
        server.starttls()
        server.ehlo()
        return server


for _register in (auth_routes.register_routes, employee_routes.register_routes, manager_routes.register_routes, admin_routes.register_routes):
        _register(app)
