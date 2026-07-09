from flask import Flask, render_template, redirect, url_for, flash, request, send_file, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from src.adapters.orm import start_mappers, metadata
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer import services
from src.service_layer.absence_processor import process_daily_absences
from src.entrypoints.forms import LoginForm, RegisterForm, ProfileForm, WorkScheduleForm, JourneyTypeForm
from src.domain.model import User, PontoStatus, JourneyType, AuditLog, CompanySettings, UserProfile
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import create_engine
from datetime import datetime, date
import smtplib
import json
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from itsdangerous import URLSafeTimedSerializer
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder='templates')
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

database_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
if not database_url:
    if os.environ.get("VERCEL"):
        # Vercel filesystem is read-only except for /tmp
        database_url = "sqlite:////tmp/banco_de_horas.db"
    else:
        database_url = "sqlite:///banco_de_horas.db"

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url

app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")

# Initialize DB and Mappers
engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])

# Start mappers early
try:
    start_mappers()
except Exception:
    # Mappers might already be started in some environments/tests
    pass

metadata.create_all(engine)

# Seed holidays on startup
try:
    with SqlAlchemyUnitOfWork() as init_uow:
        services.seed_holidays(init_uow)
except Exception as e:
    import sys
    print(f"Error seeding holidays on startup: {e}", file=sys.stderr)

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
    """Load a user for Flask-Login.
    Handles case-insensitive role values by normalizing stored role to lowercase.
    """
    # Use Unit of Work context to ensure repositories are available
    with SqlAlchemyUnitOfWork() as uow:
        try:
            user = uow.users.get_user_by_id(int(user_id))
            if user:
                return AuthenticatedUser(user)
        except LookupError:
            # Role may have incorrect case; fetch raw record and fix
            with uow.session.begin():
                raw_user = uow.session.execute(
                    "SELECT * FROM users WHERE id = :uid",
                    {"uid": int(user_id)}
                ).first()
                if raw_user and hasattr(raw_user, "role"):
                    # Normalize role to lowercase
                    normalized_role = raw_user.role.lower()
                    uow.session.execute(
                        "UPDATE users SET role = :role WHERE id = :uid",
                        {"role": normalized_role, "uid": int(user_id)}
                    )
                    uow.session.commit()
                    # Reload user after fix
                    user = uow.users.get_user_by_id(int(user_id))
                    if user:
                        return AuthenticatedUser(user)
        except (ValueError, TypeError):
            return None
        return None

@app.before_request
def run_daily_absences_check():
    # Only run for actual routes, skip static files to avoid extra overhead
    if request.endpoint and not request.endpoint.startswith('static'):
        uow = SqlAlchemyUnitOfWork()
        try:
            process_daily_absences(uow)
        except Exception as e:
            import sys
            print(f"Error running daily absences check: {e}", file=sys.stderr)

@app.context_processor
def utility_processor():
    def get_role_label(role_value, user_email=None):
        if role_value == 'manager' and user_email == 'nagelalima1307.smdcti@gmail.com':
            return 'Gestor'
            
        mapping = {
            'employee': 'Funcionário',
            'manager': 'Diretor',
            'admin': 'Secretário'
        }
        return mapping.get(role_value, role_value)
    return dict(get_role_label=get_role_label)

@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        uow = SqlAlchemyUnitOfWork()
        with uow:
            try:
                user = uow.users.get_user_by_id(int(current_user.id))
                if user:
                    # Pre-convert to dictionaries to avoid DetachedInstanceError in template
                    notifs = [
                        {"message": n.message, "is_read": n.is_read, "created_at": n.created_at} 
                        for n in user.notifications[:20]
                    ]
                    return {
                        "user_notifs": notifs,
                        "user_notifs_count": user.unread_notifications_count
                    }
            except (ValueError, TypeError):
                pass
    return {"user_notifs": [], "user_notifs_count": 0}

import sys

def send_email(to_email, subject, body_html):
    # API-based email sending via Brevo commented out per request
    # api_key = os.environ.get("BREVO_API_KEY")
    # sender_email = os.environ.get("BREVO_SENDER") or os.environ.get("MAIL_USERNAME")
    # ...
    
    # SMTP implementation optimized for serverless environments (Vercel)
    # Serverless platforms like Vercel have short execution limits, so we use short, explicit timeouts
    # and clean SMTP connection closure.
    if not app.config.get("MAIL_USERNAME") or not app.config.get("MAIL_PASSWORD"):
        print("SMTP Error: MAIL_USERNAME or MAIL_PASSWORD not configured.", file=sys.stderr)
        return False

    msg = MIMEMultipart()
    sender_display = "Banco de Horas"
    msg["From"] = f"{sender_display} <{app.config['MAIL_USERNAME']}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    
    msg.attach(MIMEText(body_html, "html"))
    
    try:
        port = app.config["MAIL_PORT"]
        server_host = app.config["MAIL_SERVER"]
        
        print(f"DEBUG: Attempting serverless-optimized SMTP to {to_email} via {server_host}:{port}...", file=sys.stderr)
        
        if port == 465:
            server = smtplib.SMTP_SSL(server_host, port, timeout=8)
        else:
            server = smtplib.SMTP(server_host, port, timeout=8)
            server.ehlo()
            server.starttls()
            server.ehlo()
            
        server.login(app.config["MAIL_USERNAME"], app.config["MAIL_PASSWORD"])
        server.send_message(msg)
        try:
            server.quit()
        except Exception:
            # Serverless environments sometimes drop the connection before quit completes; safe to ignore
            pass
        print(f"DEBUG: Email sent successfully via SMTP to {to_email}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"Detailed SMTP Error for {to_email}: {str(e)}", file=sys.stderr)
        return False

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        uow = SqlAlchemyUnitOfWork()
        with uow:
            user = uow.users.get_user_by_email(email)
            if user:
                token = serializer.dumps(email, salt="password-reset-salt")
                reset_url = url_for("reset_password", token=token, _external=True)
                html = render_template("emails/reset_password.html", reset_url=reset_url)
                if send_email(email, "Recuperação de Senha - Banco de Horas", html):
                    flash("Se o e-mail estiver cadastrado, você receberá um link de recuperação em instantes.", "info")
                else:
                    flash("Erro ao enviar o e-mail de recuperação. Por favor, tente novamente mais tarde.", "danger")
            else:
                flash("Se o e-mail estiver cadastrado, você receberá um link de recuperação em instantes.", "info")
            return redirect(url_for("login"))
    return render_template("forgot_password.html")

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = serializer.loads(token, salt="password-reset-salt", max_age=3600) # 1 hora
    except:
        flash("O link de recuperação é inválido ou expirou.", "danger")
        return redirect(url_for("forgot_password"))
    
    if request.method == "POST":
        password = request.form.get("password")
        if not password:
            flash("A senha é obrigatória.", "danger")
            return render_template("reset_password.html", token=token)
            
        uow = SqlAlchemyUnitOfWork()
        with uow:
            user = uow.users.get_user_by_email(email)
            if user:
                user.password_hash = generate_password_hash(password)
                uow.commit()
                flash("Sua senha foi atualizada com sucesso.", "success")
                return redirect(url_for("login"))
    
    return render_template("reset_password.html", token=token)

@app.route("/magic-login", methods=["POST"])
def magic_login():
    email = request.form.get("email")
    if not email:
        flash("E-mail é obrigatório.", "warning")
        return redirect(url_for("login"))
        
    uow = SqlAlchemyUnitOfWork()
    with uow:
        user = uow.users.get_user_by_email(email)
        if user:
            token = serializer.dumps(email, salt="magic-login-salt")
            login_url = url_for("magic_link_login", token=token, _external=True)
            html = render_template("emails/magic_link.html", login_url=login_url)
            if send_email(email, "Link de Acesso Rápido - Banco de Horas", html):
                flash("Se o e-mail estiver cadastrado, você receberá um link de acesso em instantes.", "info")
            else:
                flash("Erro ao enviar o e-mail de acesso. Por favor, tente novamente mais tarde.", "danger")
        else:
            flash("Se o e-mail estiver cadastrado, você receberá um link de acesso em instantes.", "info")
        
        return redirect(url_for("login"))

@app.route("/login-link/<token>")
def magic_link_login(token):
    try:
        email = serializer.loads(token, salt="magic-login-salt", max_age=600) # 10 minutos
    except:
        flash("O link de acesso é inválido ou expirou.", "danger")
        return redirect(url_for("login"))
        
    uow = SqlAlchemyUnitOfWork()
    with uow:
        user = uow.users.get_user_by_email(email)
        if user:
            login_user(AuthenticatedUser(user))
            if not user.is_profile_complete:
                return redirect(url_for("complete_profile"))
            if user.role == "employee" and not user.work_schedule:
                return redirect(url_for("choose_journey"))
            return redirect(url_for("dashboard"))
            
    flash("Usuário não encontrado.", "danger")
    return redirect(url_for("login"))

@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "static"),
                               "favicon.ico", mimetype="image/vnd.microsoft.icon")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        uow = SqlAlchemyUnitOfWork()
        with uow:
            user = uow.users.get_user_by_email(form.email.data)
            if user and check_password_hash(user.password_hash, form.password.data):
                login_user(AuthenticatedUser(user))
                if not user.is_profile_complete:
                    return redirect(url_for("complete_profile"))
                if user.role == "employee" and not user.work_schedule:
                    return redirect(url_for("choose_journey"))
                return redirect(url_for("dashboard"))
            flash("E-mail ou senha inválidos", "danger")
    return render_template("login.html", form=form)

from src.entrypoints.decorators import manager_required, admin_required, handle_errors

@app.route("/register", methods=["GET", "POST"])
@login_required
@manager_required
@handle_errors
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            uow = SqlAlchemyUnitOfWork()
            is_new = False
            try:
                services.register_user(uow, form.email.data, role=form.role.data, registered_by_id=current_user.id)
                is_new = True
            except ValueError as e:
                if "already exists" in str(e).lower():
                    is_new = False
                else:
                    raise e

            # Send invitation email (regardless of is_new, as per request)
            token = serializer.dumps(form.email.data, salt="password-reset-salt")
            setup_url = url_for("reset_password", token=token, _external=True)
            html = render_template("emails/welcome_invite.html", setup_url=setup_url)

            if send_email(form.email.data, "Bem-vindo ao Banco de Horas - Ative sua conta", html):
                if is_new:
                    flash("Usuário cadastrado! Um convite foi enviado por e-mail.", "success")
                else:
                    flash("O usuário já estava cadastrado. O convite foi reenviado com sucesso.", "info")
            else:
                # Fallback: Exibir o link na tela se o e-mail falhar
                status_msg = "Usuário cadastrado, mas o e-mail falhou. "
                if not is_new:
                    status_msg = "O usuário já existe, mas o e-mail falhou. "
                
                flash(f"{status_msg} Copie o link de ativação: {setup_url}", "warning")
        except Exception as e:
            flash(f"Erro ao cadastrar usuário: {str(e)}", "danger")
            return render_template("register.html", form=form)
        return redirect(url_for("dashboard"))
    return render_template("register.html", form=form)

@app.route("/choose-journey", methods=["GET", "POST"])
@login_required
def choose_journey():
    if current_user.role != "employee":
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    with uow:
        user = uow.users.get_user_by_id(current_user.id)
        if user.work_schedule:
            return redirect(url_for("dashboard"))
        
        journeys = services.list_journey_types(uow)
        if not journeys:
            flash("Nenhuma jornada disponível. Por favor, crie uma jornada primeiro.", "warning")
            return redirect(url_for("manage_journeys"))


        if request.method == "POST":
            journey_id = request.form.get("journey_id")
            if journey_id:
                j = services.get_journey_type(uow, int(journey_id))
                if j:
                    services.set_work_schedule(
                        uow, current_user.id, current_user.id,
                        j.expected_arrival,
                        j.expected_lunch_start,
                        j.expected_lunch_end,
                        j.expected_departure,
                        j.tolerance_minutes
                    )
                    flash("Jornada de trabalho selecionada com sucesso!", "success")
                    return redirect(url_for("dashboard"))
            flash("Por favor, selecione uma jornada.", "warning")

        return render_template("set_schedule.html", employee=user, journeys=journeys, self_select=True)

@app.route("/complete-profile", methods=["GET", "POST"])
@login_required
def complete_profile():
    if current_user.is_profile_complete:
        return redirect(url_for("dashboard"))
    
    form = ProfileForm()
    if form.validate_on_submit():
        uow = SqlAlchemyUnitOfWork()
        services.update_user_profile(
            uow,
            current_user.id,
            form.registration_number.data,
            form.cpf.data,
            form.department.data,
            form.position.data,
            form.secretariat.data,
            form.full_name.data,
            birth_date=form.birth_date.data
        )
        flash("Perfil preenchido com sucesso!", "success")
        return redirect(url_for("dashboard"))
    return render_template("complete_profile.html", form=form)

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    uow = SqlAlchemyUnitOfWork()
    with uow:
        user = uow.users.get_user_by_id(current_user.id)
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password") or None
            email_notifications = True if request.form.get("email_notifications") else False
            try:
                services.update_credentials(uow, current_user.id, email, password, email_notifications)
                
                # If Admin or Gestor, update professional profile as well
                if current_user.role in ["admin", "gestor"]:
                    analysis_date = datetime.strptime(request.form.get("start_analysis_date"), "%Y-%m-%d").date()
                    raw_birth = request.form.get("birth_date")
                    birth_date = datetime.strptime(raw_birth, "%Y-%m-%d").date() if raw_birth else None
                    services.update_user_profile(
                        uow,
                        current_user.id,
                        request.form.get("registration_number"),
                        request.form.get("cpf"),
                        request.form.get("department"),
                        request.form.get("position"),
                        request.form.get("secretariat"),
                        request.form.get("full_name"),
                        start_analysis_date=analysis_date,
                        birth_date=birth_date
                    )
                
                flash("Perfil atualizado!", "success")
                return redirect(url_for("dashboard"))
            except ValueError as e:
                msg = str(e)
                if "already exists" in msg:
                    msg = "Este e-mail já está em uso por outro usuário."
                flash(msg, "danger")
        return render_template("profile.html", user=user)

@app.route("/manager/edit-employee/<int:employee_id>", methods=["GET", "POST"])
@login_required
def edit_employee(employee_id):
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    form = ProfileForm()
    
    with uow:
        employee = uow.users.get_user_by_id(employee_id)
        if not employee:
            flash("Funcionário não encontrado.", "danger")
            return redirect(url_for("management_panel"))
        
        if form.validate_on_submit():
            services.update_user_profile(
                uow,
                employee_id,
                form.registration_number.data,
                form.cpf.data,
                form.department.data,
                form.position.data,
                form.secretariat.data,
                form.full_name.data,
                birth_date=form.birth_date.data
            )
            flash(f"Perfil de {employee.profile.full_name or employee.email} atualizado!", "success")
            return redirect(url_for("management_panel"))
        
        if not request.method == "POST":
            form.registration_number.data = employee.profile.registration_number
            form.cpf.data = employee.profile.cpf
            form.department.data = employee.profile.department
            form.position.data = employee.profile.position
            form.secretariat.data = employee.profile.secretariat
            form.full_name.data = employee.profile.full_name
            form.birth_date.data = employee.profile.birth_date
            
        return render_template("complete_profile.html", form=form, title=f"Editar Perfil: {employee.email}")

@app.route("/manager/promote/<int:user_id>", methods=["POST"])
@login_required
def promote_user(user_id):
    if current_user.role != "admin":
        flash("Acesso não autorizado", "danger")
        return redirect(url_for("dashboard"))
    uow = SqlAlchemyUnitOfWork()
    services.promote_to_manager(uow, current_user.id, user_id)
    flash("Usuário promovido a Gestor!", "success")
    return redirect(url_for("management_panel"))

@app.route("/manager/change-role/<int:user_id>", methods=["POST"])
@login_required
def change_user_role(user_id):
    if current_user.role not in ["admin", "manager", "gestor"]:
        return {"success": False, "message": "Acesso não autorizado"}, 403
    
    new_role = request.json.get("role")
    if new_role not in ["employee", "gestor", "manager", "admin"]:
        return {"success": False, "message": "Perfil inválido"}, 400
        
    uow = SqlAlchemyUnitOfWork()
    from src.domain.model import UserRole
    with uow:
        employee = uow.users.get_user_by_id(user_id)
        if employee:
            old_role = employee.role.value if hasattr(employee.role, 'value') else employee.role
            employee.role = UserRole(new_role)
            uow.commit()
            uow.record_action(
                current_user.id, 
                "PROMOTE_USER" if new_role in ["gestor", "manager", "admin"] else "DEMOTE_USER", 
                target_id=user_id, 
                details=f"Perfil alterado de {old_role} para {new_role}"
            )
            uow.commit()
            return {"success": True, "message": "Perfil atualizado com sucesso!"}
        else:
            return {"success": False, "message": "Usuário não encontrado"}, 404

@app.route("/manager/demote/<int:user_id>", methods=["POST"])
@login_required
def demote_user(user_id):
    if current_user.role != "admin":
        flash("Acesso não autorizado", "danger")
        return redirect(url_for("dashboard"))
    uow = SqlAlchemyUnitOfWork()
    services.demote_to_employee(uow, current_user.id, user_id)
    flash("Usuário rebaixado para Funcionário!", "warning")
    return redirect(url_for("management_panel"))

def get_maps_url(location_str):
    if not location_str or "," not in location_str:
        return None
    return f"https://www.google.com/maps?q={location_str.strip()}&output=embed"

@app.route("/dashboard")
@login_required
def dashboard():
    if not current_user.is_profile_complete:
        return redirect(url_for("complete_profile"))
    
    if current_user.role == "employee" and not current_user.has_schedule:
        return redirect(url_for("choose_journey"))
    
    uow = SqlAlchemyUnitOfWork()
    filter_date_str = request.args.get("date")
    filter_date = None
    if filter_date_str:
        try:
            filter_date = datetime.strptime(filter_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    with uow:
        user = uow.users.get_user_by_id(current_user.id)
        if not user:
             flash("Usuário não encontrado", "danger")
             return redirect(url_for("logout"))
             
        today_date = date.today()
        uow.session.refresh(user)
        
        ponto_hoje = next((p for p in user.time_entries if p.entry_date == today_date), None)
        current_stage = ponto_hoje.current_stage if ponto_hoje else "Chegada"
        
        last_clock_time = None
        if ponto_hoje:
            times = [ponto_hoje.departure, ponto_hoje.lunch_end, ponto_hoje.lunch_start, ponto_hoje.arrival]
            last_clock_time = next((t.strftime("%H:%M:%S") for t in times if t is not None), None)
        
        if filter_date:
            recent_entries = [p for p in user.time_entries if p.entry_date == filter_date]
        else:
            recent_entries = sorted(user.time_entries, key=lambda x: x.entry_date, reverse=True)[:10]
        
        # Calculate balances
        if user.work_schedule:
            def delta(t1, t2):
                if not t1 or not t2: return 0
                return int((datetime.combine(date.min, t2) - datetime.combine(date.min, t1)).total_seconds() / 60)
            
            expected_daily = (delta(user.work_schedule.expected_arrival, user.work_schedule.expected_lunch_start) + 
                              delta(user.work_schedule.expected_lunch_end, user.work_schedule.expected_departure))
            
            saldo_total = user.total_balance
            
            if ponto_hoje:
                saldo_dia = ponto_hoje.worked_minutes - expected_daily
            else:
                saldo_dia = 0
        else:
            expected_daily = 0
            saldo_total = 0
            saldo_dia = 0

        maps_url = None
        if ponto_hoje and ponto_hoje.location_data:
            locs = ponto_hoje.location_data.split("|")
            last_loc = locs[-1].split(":")[-1].strip()
            maps_url = get_maps_url(last_loc)

        if ponto_hoje:
            worked_hoje = ponto_hoje.worked_minutes
        else:
            worked_hoje = 0

        # Prepare schedule for template
        sched_data = None
        if user.work_schedule:
            sched_data = {
                "expected_arrival": user.work_schedule.expected_arrival.strftime("%H:%M"),
                "expected_lunch_start": user.work_schedule.expected_lunch_start.strftime("%H:%M") if user.work_schedule.expected_lunch_start else None,
                "expected_lunch_end": user.work_schedule.expected_lunch_end.strftime("%H:%M") if user.work_schedule.expected_lunch_end else None,
                "expected_departure": user.work_schedule.expected_departure.strftime("%H:%M"),
                "has_lunch_break": user.work_schedule.has_lunch_break
            }

        return render_template("employee_dashboard.html", 
                             recent_entries=recent_entries, 
                             current_stage=current_stage,
                             sched_data=sched_data,
                             maps_url=maps_url,
                             filter_date=filter_date_str,
                             saldo_dia=saldo_dia,
                             expected_daily=expected_daily,
                             saldo_total=saldo_total,
                             worked_hoje=worked_hoje,
                             ponto_hoje=ponto_hoje,
                             last_clock_time=last_clock_time)

@app.route("/manager/archive-justification/<int:employee_id>/<string:entry_date>", methods=["POST"])
@login_required
@manager_required
@handle_errors
def archive_justification(employee_id, entry_date):
    e_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
    uow = SqlAlchemyUnitOfWork()
    services.dismiss_justification(uow, current_user.id, employee_id, e_date)
    flash("Justificativa arquivada com sucesso.", "info")
    return redirect(url_for("management_panel"))

@app.route("/manager/archived-justifications", methods=["GET"])
@login_required
@manager_required
@handle_errors
def archived_justifications():
    employee_id = request.args.get("employee_id")
    date_str = request.args.get("date")
    uow = SqlAlchemyUnitOfWork()
    with uow:
        employees = services.get_all_employees(uow, requester_id=int(current_user.id))
        archived = [
            {"emp": e, "ponto": p} for e in employees 
            for p in e.time_entries if p.status == PontoStatus.DISMISSED
        ]
        if employee_id:
            archived = [a for a in archived if a['emp'].user_id == int(employee_id)]
        if date_str:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            archived = [a for a in archived if a['ponto'].entry_date == target_date]
        return render_template("archived_justifications.html", archived_justs=archived, employees=employees, selected_emp=int(employee_id) if employee_id else None, selected_date=date_str)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/manager/archive-justification-action/<int:employee_id>/<string:entry_date>", methods=["POST"])
@login_required
@manager_required
@handle_errors
def archive_justification_action(employee_id, entry_date):
    e_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
    uow = SqlAlchemyUnitOfWork()
    services.dismiss_justification(uow, current_user.id, employee_id, e_date)
    flash("Justificativa arquivada com sucesso.", "info")
    return redirect(url_for("management_panel"))

@app.route("/management")
@login_required
def management_panel():
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso restrito.", "danger")
        return redirect(url_for("dashboard"))
        
    uow = SqlAlchemyUnitOfWork()
    with uow:
        employees = services.get_all_employees(uow, requester_id=int(current_user.id))
        for e in employees:
            uow.session.refresh(e)
            
        pending_anomalies = [p for e in employees for p in e.time_entries if p.has_anomaly]
        emp_filter = request.args.get("emp_filter")
        date_filter = request.args.get("date_filter")
        
        pending_anomalies = [
            {"emp": e, "ponto": p} for e in employees 
            for p in e.time_entries if p.has_anomaly and p.status != PontoStatus.CORRECTED
        ]
        
        if emp_filter:
            pending_anomalies = [a for a in pending_anomalies if a['emp'].user_id == int(emp_filter)]
        if date_filter:
            f_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
            pending_anomalies = [a for a in pending_anomalies if a['ponto'].entry_date == f_date]

        dismissed_justs = [
            {"emp": e, "ponto": e.time_entries} for e in employees 
            # Simplified filtering - needs review in a real production env
        ]
        # Re-using the logic from previous commits for simplicity
        dismissed_justs = [
            {"emp": e, "ponto": p} for e in employees 
            for p in e.time_entries if p.status == PontoStatus.DISMISSED
        ]
        
        pending_corrections = services.list_pending_corrections(uow, int(current_user.id))
        analysis_date = services.get_start_analysis_date(uow)
        
        corrections_display = []
        for c in pending_corrections:
            user = uow.users.get_user_by_id(c.user_id)
            corrections_display.append({
                "id": c.request_id,
                "user_name": user.profile.full_name or user.email,
                "date": c.ponto_date,
                "stage": c.stage,
                "time": c.proposed_time
            })

        from src.domain.model import Holiday
        holidays_list = uow.session.query(Holiday).order_by(Holiday.holiday_date).all()
        holidays_serialized = [{"date": h.holiday_date.strftime("%Y-%m-%d"), "description": h.description} for h in holidays_list]

        return render_template("manager_dashboard.html", 
                             employees=employees, 
                             today=date.today(),
                             analysis_date=analysis_date,
                             pending_anomalies=pending_anomalies,
                             dismissed_justs=dismissed_justs,
                             pending_corrections=corrections_display,
                             holidays=holidays_serialized)

@app.route("/admin/update-user-analysis-date/<int:employee_id>", methods=["POST"])
@login_required
def update_user_analysis_date(employee_id):
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso restrito.", "danger")
        return redirect(url_for("dashboard"))
    
    start_date = datetime.strptime(request.form.get("start_analysis_date"), "%Y-%m-%d").date()
    uow = SqlAlchemyUnitOfWork()
    with uow:
        employee = uow.users.get_user_by_id(employee_id)
        if employee:
            employee.profile = UserProfile(
                registration_number=employee.profile.registration_number,
                cpf=employee.profile.cpf,
                department=employee.profile.department,
                position=employee.profile.position,
                secretariat=employee.profile.secretariat,
                full_name=employee.profile.full_name,
                start_analysis_date=start_date
            )
            uow.commit()
            flash(f"Data de início de análise de {employee.profile.full_name or employee.email} atualizada.", "success")
        else:
            flash("Funcionário não encontrado.", "danger")
    
    return redirect(url_for("view_employee_logs", employee_id=employee_id))


@app.route("/submit-correction", methods=["POST"])
@login_required
def submit_correction():
    try:
        ponto_date = datetime.strptime(request.form.get("ponto_date"), "%Y-%m-%d").date()
        stage = request.form.get("stage")
        proposed_time = datetime.strptime(request.form.get("proposed_time"), "%H:%M").time()
        
        uow = SqlAlchemyUnitOfWork()
        services.submit_correction_request(uow, current_user.id, ponto_date, stage, proposed_time)
        flash("Pedido de correção enviado para análise.", "success")
    except Exception as e:
        flash(f"Erro ao enviar correção: {str(e)}", "danger")
    return redirect(url_for("dashboard"))

@app.route("/notifications/read", methods=["POST"])
@login_required
def mark_notifications_read():
    uow = SqlAlchemyUnitOfWork()
    services.mark_notifications_as_read(uow, current_user.id)
    return {"status": "ok"}

@app.route("/clock", methods=["POST"])
@login_required
def clock():
    location = request.form.get("location")
    stage = request.form.get("stage")
    notes = request.form.get("notes")
    uow = SqlAlchemyUnitOfWork()
    try:
        msg = services.clock_in_out(uow, current_user.id, location, stage=stage, notes=notes)
        flash(msg, "info")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("dashboard"))

@app.route("/update-note", methods=["POST"])
@login_required
def update_note():
    try:
        entry_date = datetime.strptime(request.form.get("entry_date"), "%Y-%m-%d").date()
        notes = request.form.get("notes")
        
        uow = SqlAlchemyUnitOfWork()
        with uow:
            user = uow.users.get_user_by_id(current_user.id)
            ponto = next((p for p in user.time_entries if p.entry_date == entry_date), None)
            if ponto:
                ponto.notes = notes
                uow.commit()
                flash("Nota atualizada com sucesso.", "success")
            else:
                flash("Registro não encontrado.", "warning")
    except Exception as e:
        flash(f"Erro ao salvar nota: {str(e)}", "danger")
    return redirect(url_for("dashboard"))

@app.route("/manager/review-correction/<int:request_id>/<string:action>", methods=["POST"])
@login_required
def review_correction(request_id, action):
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    approved = (action == "approve")
    uow = SqlAlchemyUnitOfWork()
    try:
        services.review_correction_request(uow, current_user.id, request_id, approved)
        flash("Correção processada com sucesso.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    
    return redirect(url_for("management_panel"))

@app.route("/download-report/<int:user_id>")
@login_required
def download_report(user_id):
    if current_user.id != user_id and current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    start_date = None
    end_date = None

    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Formato de data inválido.", "danger")
        return redirect(url_for("dashboard"))

    uow = SqlAlchemyUnitOfWork()
    excel_file = services.generate_excel_report(uow, user_id, start_date, end_date)
    
    with uow:
        user = uow.users.get_user_by_id(user_id)
        emp_name = (user.profile.full_name or "funcionario").replace(" ", "_").lower() if user and user.profile else "funcionario"

    start_str = start_date.strftime('%Y%m%d') if start_date else 'inicio'
    end_str = end_date.strftime('%Y%m%d') if end_date else 'fim'
    filename = f"relatorio_{emp_name}_{start_str}_{end_str}.xlsx"
    
    return send_file(
        excel_file,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
@app.route("/manager/view-logs/<int:employee_id>")
@login_required
def view_employee_logs(employee_id):
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    with uow:
        employee = uow.users.get_user_by_id(employee_id)
        if not employee:
            flash("Funcionário não encontrado.", "danger")
            return redirect(url_for("dashboard"))
        
        uow.session.refresh(employee)
        recent_entries = sorted(employee.time_entries, key=lambda x: x.entry_date, reverse=True)
        return render_template("view_employee_logs.html", employee=employee, recent_entries=recent_entries)

@app.route("/manager/bulk-fix-ponto/<int:employee_id>", methods=["POST"])
@login_required
def bulk_fix_ponto(employee_id):
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))

    uow = SqlAlchemyUnitOfWork()
    dates = request.form.getlist("dates")
    emp_ids = request.form.getlist("emp_ids")
    selected_points = request.form.getlist("selected_points")
    
    def parse_time(val):
        if not val: return None
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(val, fmt).time()
            except ValueError:
                continue
        return None

    try:
        # If emp_ids are provided (from bulk anomaly form), iterate over them
        if emp_ids and len(emp_ids) == len(dates):
            for i, entry_date_str in enumerate(dates):
                emp_id = int(emp_ids[i])
                key = f"{emp_id}_{entry_date_str}"
                if key not in selected_points:
                    continue
                entry_date = datetime.strptime(entry_date_str, "%Y-%m-%d").date()
                arrival = parse_time(request.form.get(f"arrival_{emp_id}_{entry_date_str}"))
                lunch_start = parse_time(request.form.get(f"lunch_start_{emp_id}_{entry_date_str}"))
                lunch_end = parse_time(request.form.get(f"lunch_end_{emp_id}_{entry_date_str}"))
                departure = parse_time(request.form.get(f"departure_{emp_id}_{entry_date_str}"))

                services.manual_ponto_correction(
                    uow, current_user.id, emp_id, entry_date,
                    arrival, lunch_start, lunch_end, departure,
                    manager_notes=request.form.get(f"manager_notes_{entry_date_str}")
                )
        else:
            # Fallback to single employee from route param
            for entry_date_str in dates:
                if entry_date_str not in selected_points:
                    continue
                entry_date = datetime.strptime(entry_date_str, "%Y-%m-%d").date()
                arrival = parse_time(request.form.get(f"arrival_{entry_date_str}"))
                lunch_start = parse_time(request.form.get(f"lunch_start_{entry_date_str}"))
                lunch_end = parse_time(request.form.get(f"lunch_end_{entry_date_str}"))
                departure = parse_time(request.form.get(f"departure_{entry_date_str}"))
                manager_notes = request.form.get(f"manager_notes_{entry_date_str}")

                services.manual_ponto_correction(
                    uow, current_user.id, employee_id, entry_date,
                    arrival, lunch_start, lunch_end, departure,
                    manager_notes=manager_notes
                )
        flash("Registros selecionados atualizados com sucesso.", "success")
    except Exception as e:
        flash(f"Erro ao processar correções: {str(e)}", "danger")

    if employee_id != 0:
        return redirect(url_for("view_employee_logs", employee_id=employee_id))
    return redirect(url_for("management_panel"))

@app.route("/manager/fix-ponto/<int:employee_id>", methods=["GET", "POST"])
@login_required
def fix_ponto(employee_id):
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))

    uow = SqlAlchemyUnitOfWork()
    if request.method == "POST":
        entry_date = datetime.strptime(request.form.get("entry_date"), "%Y-%m-%d").date()
        
        def parse_time(val):
            if not val: return None
            for fmt in ("%H:%M:%S", "%H:%M"):
                try:
                    return datetime.strptime(val, fmt).time()
                except ValueError:
                    continue
            return None

        services.manual_ponto_correction(
            uow,
            current_user.id,
            employee_id,
            entry_date,
            parse_time(request.form.get("arrival")),
            parse_time(request.form.get("lunch_start")),
            parse_time(request.form.get("lunch_end")),
            parse_time(request.form.get("departure")),
            email_sender=send_email
        )
        flash("Registro corrigido manualmente.", "success")
        return redirect(url_for("view_employee_logs", employee_id=employee_id))

    with uow:
        employee = uow.users.get_user_by_id(employee_id)
        return render_template("fix_ponto.html", employee=employee, today=date.today())

@app.route("/manager/add-vacation/<int:employee_id>", methods=["POST"])
@login_required
def add_vacation(employee_id):
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d").date()
    end_date = datetime.strptime(request.form.get("end_date"), "%Y-%m-%d").date()
    
    uow = SqlAlchemyUnitOfWork()
    services.add_vacation(uow, current_user.id, employee_id, start_date, end_date)
    flash("Período de férias adicionado.", "success")
    return redirect(url_for("dashboard"))

@app.route("/manager/add-holiday", methods=["POST"])
@login_required
def add_holiday():
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    h_date = datetime.strptime(request.form.get("holiday_date"), "%Y-%m-%d").date()
    desc = request.form.get("description")
    mandatory = request.form.get("is_mandatory") == "on"
    
    uow = SqlAlchemyUnitOfWork()
    services.add_holiday(uow, current_user.id, h_date, desc, mandatory)
    flash("Feriado adicionado.", "success")
    return redirect(url_for("dashboard"))

@app.route("/manager/delete-user/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    services.delete_user(uow, current_user.id, user_id)
    flash("Usuário excluído.", "warning")
    return redirect(url_for("management_panel"))

@app.route("/manager/reset-user-password/<int:user_id>", methods=["POST"])
@login_required
def reset_user_password(user_id):
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    with uow:
        user = uow.users.get_user_by_id(user_id)
        if not user:
            flash("Usuário não encontrado.", "danger")
            return redirect(url_for("management_panel"))
        
        token = serializer.dumps(user.email, salt="password-reset-salt")
        reset_url = url_for("reset_password", token=token, _external=True)
        
        # Optionally send via email as well
        html = render_template("emails/reset_password.html", reset_url=reset_url)
        if send_email(user.email, "Redefinição de Senha Solicitada", html):
            flash(f"Link de redefinição enviado para o e-mail do usuário.", "success")
        else:
            flash(f"Não foi possível enviar o e-mail. Link de redefinição: {reset_url}", "warning")
            
    return redirect(url_for("view_employee_logs", employee_id=user_id))

@app.route("/manager/set-schedule/<int:employee_id>", methods=["GET", "POST"])
@login_required
def set_schedule(employee_id):
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))

    uow = SqlAlchemyUnitOfWork()
    form = WorkScheduleForm()
    
    with uow:
        journeys = services.list_journey_types(uow)
        form.journey_type.choices = [(0, "Selecione um template...")] + [(j.journey_id, j.name) for j in journeys]

    if form.validate_on_submit():
        def parse_time(val):
            if not val: return None
            return datetime.strptime(val, "%H:%M").time()

        try:
            journey_id = int(request.form.get("journey_type", 0))
            rotation_start = None
            if form.rotation_start_date.data:
                try:
                    rotation_start = datetime.strptime(form.rotation_start_date.data, "%Y-%m-%d").date()
                except ValueError:
                    pass

            if journey_id > 0:
                with uow:
                    j = services.get_journey_type(uow, journey_id)
                    if j:
                        arr, l_s, l_e, dep, tol, has_lunch, s_type = j.expected_arrival, j.expected_lunch_start, j.expected_lunch_end, j.expected_departure, j.tolerance_minutes, j.has_lunch_break, j.schedule_type.value
                    else:
                        raise ValueError("Modelo de jornada não encontrado.")
            else:
                arr = parse_time(form.arrival.data)
                l_s = parse_time(form.lunch_start.data)
                l_e = parse_time(form.lunch_end.data)
                dep = parse_time(form.departure.data)
                tol = int(form.tolerance.data)
                has_lunch = form.has_lunch_break.data
                s_type = form.schedule_type.data

            services.set_work_schedule(uow, current_user.id, employee_id, arr, l_s, l_e, dep, tol, has_lunch_break=has_lunch, schedule_type=s_type, rotation_start_date=rotation_start)

            if journey_id == 0 and form.save_as_new.data:
                services.create_journey_type(uow, current_user.id, form.save_as_new.data, arr, l_s, l_e, dep, tol, has_lunch_break=has_lunch, schedule_type=s_type)
                flash(f"Template '{form.save_as_new.data}' salvo!", "info")
            flash("Horário de trabalho configurado.", "success")
            return redirect(url_for("view_employee_logs", employee_id=employee_id))
        except Exception as e:
            flash(f"Erro: {str(e)}", "danger")

    with uow:
        employee = uow.users.get_user_by_id(employee_id)
        if not request.method == "POST" and employee.work_schedule:
            form.arrival.data = employee.work_schedule.expected_arrival.strftime("%H:%M")
            form.has_lunch_break.data = employee.work_schedule.has_lunch_break
            form.lunch_start.data = employee.work_schedule.expected_lunch_start.strftime("%H:%M") if employee.work_schedule.expected_lunch_start else ""
            form.lunch_end.data = employee.work_schedule.expected_lunch_end.strftime("%H:%M") if employee.work_schedule.expected_lunch_end else ""
            form.departure.data = employee.work_schedule.expected_departure.strftime("%H:%M")
            form.tolerance.data = str(employee.work_schedule.tolerance_minutes)
        
        journeys = services.list_journey_types(uow)
        return render_template("set_schedule.html", form=form, employee=employee, journeys=journeys)

@app.route("/manager/journey-types", methods=["GET", "POST"])
@login_required
def manage_journeys():
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    form = JourneyTypeForm()
    
    if form.validate_on_submit():
        def parse_time(val):
            if not val: return None
            return datetime.strptime(val, "%H:%M").time()
        
        services.create_journey_type(
            uow, current_user.id, form.name.data,
            parse_time(form.arrival.data),
            parse_time(form.lunch_start.data),
            parse_time(form.lunch_end.data),
            parse_time(form.departure.data),
            int(form.tolerance.data),
            has_lunch_break=form.has_lunch_break.data,
            schedule_type=form.schedule_type.data
        )
        flash("Tipo de Jornada criado.", "success")
        return redirect(url_for("management_panel"))
    
    with uow:
        journeys = services.list_journey_types(uow)
        return render_template("manage_journeys.html", form=form, journeys=journeys)

@app.route("/manager/get-journey/<int:journey_id>")
@login_required
def get_journey_json(journey_id):
    if current_user.role not in ["manager", "admin", "gestor"]:
        return {"error": "Unauthorized"}, 403
    
    uow = SqlAlchemyUnitOfWork()
    j = services.get_journey_type(uow, journey_id)
    if not j:
        return {"error": "Not found"}, 404
    
    return {
        "arrival": j.expected_arrival.strftime("%H:%M"),
        "has_lunch_break": j.has_lunch_break,
        "lunch_start": j.expected_lunch_start.strftime("%H:%M") if j.expected_lunch_start else "",
        "lunch_end": j.expected_lunch_end.strftime("%H:%M") if j.expected_lunch_end else "",
        "departure": j.expected_departure.strftime("%H:%M"),
        "tolerance": j.tolerance_minutes,
        "schedule_type": j.schedule_type.value
    }

@app.route("/manager/edit-journey/<int:journey_id>", methods=["GET", "POST"])
@login_required
def edit_journey(journey_id):
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    form = JourneyTypeForm()
    
    if form.validate_on_submit():
        def parse_time(val):
            if not val: return None
            return datetime.strptime(val, "%H:%M").time()
        
        try:
            services.update_journey_type(
                uow, current_user.id, journey_id, form.name.data,
                parse_time(form.arrival.data),
                parse_time(form.lunch_start.data),
                parse_time(form.lunch_end.data),
                parse_time(form.departure.data),
                int(form.tolerance.data),
                has_lunch_break=form.has_lunch_break.data,
                schedule_type=form.schedule_type.data
            )
            flash("Tipo de Jornada atualizado.", "success")
            return redirect(url_for("manage_journeys"))
        except Exception as e:
            flash(f"Erro: {str(e)}", "danger")

    with uow:
        j = services.get_journey_type(uow, journey_id)
        if not j:
            flash("Jornada não encontrada.", "danger")
            return redirect(url_for("manage_journeys"))
        
        if not request.method == "POST":
            form.name.data = j.name
            form.has_lunch_break.data = j.has_lunch_break
            form.arrival.data = j.expected_arrival.strftime("%H:%M")
            form.lunch_start.data = j.expected_lunch_start.strftime("%H:%M") if j.expected_lunch_start else ""
            form.lunch_end.data = j.expected_lunch_end.strftime("%H:%M") if j.expected_lunch_end else ""
            form.departure.data = j.expected_departure.strftime("%H:%M")
            form.tolerance.data = str(j.tolerance_minutes)
            form.schedule_type.data = j.schedule_type.value
        
        return render_template("edit_journey.html", form=form, journey=j)

@app.route("/manager/delete-journey/<int:journey_id>", methods=["POST"])
@login_required
def delete_journey(journey_id):
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    services.delete_journey_type(uow, current_user.id, journey_id)
    flash("Tipo de Jornada excluído.", "warning")
    return redirect(url_for("manage_journeys"))


    
    target_date_str = request.form.get("target_date")
    if not target_date_str:
        flash("Data não fornecida.", "warning")
        return redirect(url_for("dashboard"))
        
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    uow = SqlAlchemyUnitOfWork()
    services.generate_missing_logs(uow, current_user.id, target_date)
    flash(f"Faltas processadas para {target_date}.", "info")
    return redirect(url_for("dashboard"))


    
    approved = request.form.get("justified") == "true"
    e_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
    
    uow = SqlAlchemyUnitOfWork()
    try:
        services.review_justification(uow, current_user.id, employee_id, e_date, approved, email_sender=send_email)
        flash("Status atualizado.", "success")
    except ValueError as e:
        flash(str(e), "danger")
        
    return redirect(url_for("dashboard"))

@app.route("/admin/audit-logs")
@login_required
def audit_logs():
    if current_user.role not in ["admin", "gestor"]:
        flash("Acesso restrito ao Administrador.", "danger")
        return redirect(url_for("dashboard"))

    actor_search = request.args.get("actor_search")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    action_type = request.args.get("action_type")

    uow = SqlAlchemyUnitOfWork()
    with uow:
        # Join with User table to filter by role
        query = uow.session.query(AuditLog).join(User, AuditLog.user_id == User.user_id)
        
        # Exclude standard employee actions
        query = query.filter(AuditLog.action.notin_(['CLOCK_EVENT', 'SUBMIT_CORRECTION_REQUEST']))
        
        # Only show actions by managers or admins
        query = query.filter(User.role.in_(['manager', 'admin', 'gestor']))

        if actor_search:
            # Join on User table ID directly since UserProfile is a composite of User
            
            # Check if input is a digit (ID) or string (Email/Name)
            if actor_search.isdigit():
                query = query.filter(AuditLog.user_id == int(actor_search))
            else:
                query = query.filter(
                    (User.email.contains(actor_search)) | 
                    (User.full_name == actor_search) |
                    (User.full_name.contains(actor_search))
                )
        
        if action_type:
            query = query.filter(AuditLog.action == action_type)

        if start_date:
            query = query.filter(AuditLog.timestamp >= datetime.strptime(start_date, "%Y-%m-%d"))
        if end_date:
            query = query.filter(AuditLog.timestamp <= datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))

        logs = query.order_by(AuditLog.timestamp.desc()).limit(200).all()
        
        logs_display = []
        for l in logs:
            actor = uow.users.get_user_by_id(l.user_id) if l.user_id else None
            target = uow.users.get_user_by_id(l.target_id) if l.target_id else None
            
            logs_display.append({
                "timestamp": l.timestamp,
                "action": l.action,
                "details": l.details,
                "actor_name": actor.profile.full_name if actor and actor.profile else (actor.email if actor else "Sistema"),
                "actor_email": actor.email if actor else "",
                "target_name": target.profile.full_name if target and target.profile else (target.email if target else ""),
                "target_email": target.email if target else ""
            })
            
        return render_template("audit_logs.html", audit_logs=logs, logs_display=logs_display)
@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def admin_settings():
    if current_user.role not in ["admin", "gestor"]:
        flash("Acesso restrito ao Administrador.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    if request.method == "POST":
        lat = float(request.form.get("lat"))
        lon = float(request.form.get("lon"))
        start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d").date()
        
        with uow:
            settings = uow.session.query(CompanySettings).first()
            if settings:
                settings.lat = lat
                settings.lon = lon
                settings.start_analysis_date = start_date
            else:
                settings = CompanySettings(lat=lat, lon=lon, start_analysis_date=start_date)
                uow.session.add(settings)
            uow.commit()
            flash("Configurações atualizadas.", "success")
            return redirect(url_for("admin_settings"))
            
    with uow:
        settings = uow.session.query(CompanySettings).first()
        return render_template("admin_settings.html", settings=settings)

@app.route("/manager/delete-ponto/<int:employee_id>/<string:entry_date>", methods=["POST"])
@login_required
def delete_ponto(employee_id, entry_date):
    if current_user.role not in ["manager", "admin", "gestor"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    e_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
    uow = SqlAlchemyUnitOfWork()
    services.delete_ponto_entry(uow, current_user.id, employee_id, e_date)
    flash("Registro de ponto excluído.", "warning")
    return redirect(url_for("view_employee_logs", employee_id=employee_id))

@app.route("/manager/review-badge/<int:employee_id>/<string:entry_date>/<string:stage>/<string:action>", methods=["POST"])
@login_required
def review_badge(employee_id, entry_date, stage, action):
    if current_user.role not in ["admin", "gestor"]:
        flash("Apenas o Administrador pode realizar esta ação.", "danger")
        return redirect(url_for("view_employee_logs", employee_id=employee_id))

    e_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
    uow = SqlAlchemyUnitOfWork()
    try:
        services.review_anomaly_badge(uow, int(current_user.id), employee_id, e_date, stage, action)
        flash("Badge de anomalia atualizado com sucesso.", "success")
    except Exception as e:
        flash(str(e), "danger")

    return redirect(url_for("view_employee_logs", employee_id=employee_id))
@app.route("/manager/save-manager-note", methods=["POST"])
@login_required
@manager_required
@handle_errors
def save_manager_note():
    employee_id = int(request.form.get("employee_id"))
    entry_date = datetime.strptime(request.form.get("entry_date"), "%Y-%m-%d").date()
    note_text = request.form.get("note_text")
    
    uow = SqlAlchemyUnitOfWork()
    services.manual_ponto_correction(
        uow, current_user.id, employee_id, entry_date,
        None, None, None, None, manager_notes=note_text
    )
    return {"status": "success"}


