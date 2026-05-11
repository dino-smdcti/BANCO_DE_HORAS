from flask import Flask, render_template, redirect, url_for, flash, request, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from src.adapters.orm import start_mappers, metadata
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer import services
from src.entrypoints.forms import LoginForm, RegisterForm, ProfileForm, WorkScheduleForm, JourneyTypeForm
from src.domain.model import User, PontoStatus, JourneyType, AuditLog, CompanySettings
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

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

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

serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class AuthenticatedUser(UserMixin):
    def __init__(self, user):
        self.id = user.user_id
        self.email = user.email
        self.role = user.role
        self.full_name = user.profile.full_name
        self.is_profile_complete = user.is_profile_complete
        self.work_schedule = user.work_schedule
        self.has_schedule = user.work_schedule is not None

@login_manager.user_loader
def load_user(user_id):
    uow = SqlAlchemyUnitOfWork()
    with uow:
        try:
            user = uow.users.get_user_by_id(int(user_id))
            if user:
                return AuthenticatedUser(user)
        except (ValueError, TypeError):
            return None
    return None

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
    # API-based email sending via Brevo (Transactional API v3)
    api_key = os.environ.get("BREVO_API_KEY")
    # Tenta BREVO_SENDER primeiro, depois MAIL_USERNAME
    sender_email = os.environ.get("BREVO_SENDER") or os.environ.get("MAIL_USERNAME")
    
    if not api_key:
        print("DEBUG: BREVO_API_KEY is missing", file=sys.stderr)
        return False
    if not sender_email:
        print("DEBUG: BREVO_SENDER/MAIL_USERNAME is missing", file=sys.stderr)
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    data = {
        "sender": {"name": "Banco de Horas", "email": sender_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": body_html
    }

    print(f"DEBUG: Attempting to send email to {to_email} via Brevo...", file=sys.stderr)

    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req) as response:
            status = response.status
            print(f"DEBUG: Brevo Response Status: {status}", file=sys.stderr)
            return status in [200, 201]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"DEBUG: Brevo API HTTP Error: {e.code} - {error_body}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"DEBUG: Brevo API Unexpected Error: {str(e)}", file=sys.stderr)
        return False

# Original SMTP implementation (Commented out)
# def send_email(to_email, subject, body_html):
#     if not app.config.get("MAIL_USERNAME") or not app.config.get("MAIL_PASSWORD"):
#         print("SMTP Error: MAIL_USERNAME or MAIL_PASSWORD not configured.")
#         return False
#
#     msg = MIMEMultipart()
#     msg["From"] = f"Banco de Horas <{app.config['MAIL_USERNAME']}>"
#     msg["To"] = to_email
#     msg["Subject"] = subject
#     
#     msg.attach(MIMEText(body_html, "html"))
#     
#     try:
#         # Determine if we should use SSL or STARTTLS based on port
#         port = app.config["MAIL_PORT"]
#         if port == 465:
#             server = smtplib.SMTP_SSL(app.config["MAIL_SERVER"], port, timeout=10)
#         else:
#             server = smtplib.SMTP(app.config["MAIL_SERVER"], port, timeout=10)
#             server.starttls()
#             
#         server.login(app.config["MAIL_USERNAME"], app.config["MAIL_PASSWORD"])
#         server.send_message(msg)
#         server.quit()
#         return True
#     except Exception as e:
#         print(f"Detailed SMTP Error for {to_email}: {str(e)}")
#         return False

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
                if send_email(email, "RecuperaÃ§Ã£o de Senha - Banco de Horas", html):
                    flash("Se o e-mail estiver cadastrado, vocÃª receberÃ¡ um link de recuperaÃ§Ã£o em instantes.", "info")
                else:
                    flash("Erro ao enviar o e-mail de recuperaÃ§Ã£o. Por favor, tente novamente mais tarde.", "danger")
            else:
                flash("Se o e-mail estiver cadastrado, vocÃª receberÃ¡ um link de recuperaÃ§Ã£o em instantes.", "info")
            return redirect(url_for("login"))
    return render_template("forgot_password.html")

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = serializer.loads(token, salt="password-reset-salt", max_age=3600) # 1 hora
    except:
        flash("O link de recuperaÃ§Ã£o Ã© invÃ¡lido ou expirou.", "danger")
        return redirect(url_for("forgot_password"))
    
    if request.method == "POST":
        password = request.form.get("password")
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
        flash("E-mail Ã© obrigatÃ³rio.", "warning")
        return redirect(url_for("login"))
        
    uow = SqlAlchemyUnitOfWork()
    with uow:
        user = uow.users.get_user_by_email(email)
        if user:
            token = serializer.dumps(email, salt="magic-login-salt")
            login_url = url_for("magic_link_login", token=token, _external=True)
            html = render_template("emails/magic_link.html", login_url=login_url)
            if send_email(email, "Link de Acesso RÃ¡pido - Banco de Horas", html):
                flash("Se o e-mail estiver cadastrado, vocÃª receberÃ¡ um link de acesso em instantes.", "info")
            else:
                flash("Erro ao enviar o e-mail de acesso. Por favor, tente novamente mais tarde.", "danger")
        else:
            flash("Se o e-mail estiver cadastrado, vocÃª receberÃ¡ um link de acesso em instantes.", "info")
        
        return redirect(url_for("login"))

@app.route("/login-link/<token>")
def magic_link_login(token):
    try:
        email = serializer.loads(token, salt="magic-login-salt", max_age=600) # 10 minutos
    except:
        flash("O link de acesso Ã© invÃ¡lido ou expirou.", "danger")
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
            
    flash("UsuÃ¡rio nÃ£o encontrado.", "danger")
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
            flash("E-mail ou senha invÃ¡lidos", "danger")
    return render_template("login.html", form=form)

@app.route("/register", methods=["GET", "POST"])
@login_required
def register():
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso restrito a gestores.", "danger")
        return redirect(url_for("dashboard"))
    
    form = RegisterForm()
    if form.validate_on_submit():
        uow = SqlAlchemyUnitOfWork()
        try:
            is_new = services.register_user(uow, form.email.data, role=form.role.data, registered_by_id=current_user.id)
            
            # Send invitation email (regardless of is_new, as per request)
            token = serializer.dumps(form.email.data, salt="password-reset-salt")
            setup_url = url_for("reset_password", token=token, _external=True)
            html = render_template("emails/welcome_invite.html", setup_url=setup_url)
            
            if send_email(form.email.data, "Bem-vindo ao Banco de Horas - Ative sua conta", html):
                if is_new:
                    flash("UsuÃ¡rio cadastrado! Um convite foi enviado por e-mail.", "success")
                else:
                    flash("O usuÃ¡rio jÃ¡ estava cadastrado. O convite foi reenviado com sucesso.", "info")
            else:
                # Fallback: Exibir o link na tela se o e-mail falhar
                status_msg = "UsuÃ¡rio cadastrado, mas o e-mail falhou. "
                if not is_new:
                    status_msg = "O usuÃ¡rio jÃ¡ existe, mas o e-mail falhou. "
                
                flash(f"{status_msg} Copie o link de ativaÃ§Ã£o: {setup_url}", "warning")
            
            return redirect(url_for("dashboard"))
        except Exception as e:
            flash(f"Ocorreu um erro inesperado: {str(e)}", "danger")
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
            form.full_name.data
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
                
                # If Admin, update professional profile as well
                if current_user.role == "admin":
                    services.update_user_profile(
                        uow,
                        current_user.id,
                        request.form.get("registration_number"),
                        request.form.get("cpf"),
                        request.form.get("department"),
                        request.form.get("position"),
                        request.form.get("secretariat"),
                        request.form.get("full_name")
                    )
                
                flash("Perfil atualizado!", "success")
                return redirect(url_for("dashboard"))
            except ValueError as e:
                msg = str(e)
                if "already exists" in msg:
                    msg = "Este e-mail jÃ¡ estÃ¡ em uso por outro usuÃ¡rio."
                flash(msg, "danger")
        return render_template("profile.html", user=user)

@app.route("/manager/edit-employee/<int:employee_id>", methods=["GET", "POST"])
@login_required
def edit_employee(employee_id):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    form = ProfileForm()
    
    with uow:
        employee = uow.users.get_user_by_id(employee_id)
        if not employee:
            flash("Funcionário nÃ£o encontrado.", "danger")
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
                form.full_name.data
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
            
        return render_template("complete_profile.html", form=form, title=f"Editar Perfil: {employee.email}")

@app.route("/manager/promote/<int:user_id>", methods=["POST"])
@login_required
def promote_user(user_id):
    if current_user.role != "admin":
        flash("Acesso nÃ£o autorizado", "danger")
        return redirect(url_for("dashboard"))
    uow = SqlAlchemyUnitOfWork()
    services.promote_to_manager(uow, current_user.id, user_id)
    flash("UsuÃ¡rio promovido a Gestor!", "success")
    return redirect(url_for("management_panel"))

@app.route("/manager/demote/<int:user_id>", methods=["POST"])
@login_required
def demote_user(user_id):
    if current_user.role != "admin":
        flash("Acesso nÃ£o autorizado", "danger")
        return redirect(url_for("dashboard"))
    uow = SqlAlchemyUnitOfWork()
    services.demote_to_employee(uow, current_user.id, user_id)
    flash("UsuÃ¡rio rebaixado para Funcionário!", "warning")
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
             flash("UsuÃ¡rio nÃ£o encontrado", "danger")
             return redirect(url_for("logout"))
             
        today_date = date.today()
        ponto_hoje = next((p for p in user.time_entries if p.entry_date == today_date), None)
        current_stage = ponto_hoje.current_stage if ponto_hoje else "Chegada"
        
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
                             worked_hoje=worked_hoje)

@app.route("/manager/dismiss-justification/<int:employee_id>/<string:entry_date>", methods=["POST"])
@login_required
def dismiss_justification(employee_id, entry_date):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    e_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
    uow = SqlAlchemyUnitOfWork()
    try:
        services.dismiss_justification(uow, current_user.id, employee_id, e_date)
        flash("Justificativa dispensada com sucesso.", "info")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("management_panel"))

@app.route("/manager/clear-anomaly/<int:employee_id>/<string:entry_date>", methods=["POST"])
@login_required
def clear_anomaly(employee_id, entry_date):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    e_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
    uow = SqlAlchemyUnitOfWork()
    try:
        services.clear_ponto_anomaly(uow, current_user.id, employee_id, e_date)
        flash("Anomalia removida com sucesso.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("view_employee_logs", employee_id=employee_id))

@app.route("/management")
@login_required
def management_panel():
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso restrito.", "danger")
        return redirect(url_for("dashboard"))
        
    uow = SqlAlchemyUnitOfWork()
    with uow:
        employees = services.get_all_employees(uow, requester_id=int(current_user.id))
        pending_justs = [p for e in employees for p in e.time_entries if p.has_anomaly and not p.justification]
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
                "time": c.proposed_time,
                "justification": c.justification
            })

        return render_template("manager_dashboard.html", 
                             employees=employees, 
                             today=date.today(),
                             analysis_date=analysis_date,
                             pending_justs={"found": len(pending_justs) > 0, "entries": pending_justs},
                             dismissed_justs=dismissed_justs,
                             pending_corrections=corrections_display)

@app.route("/admin/update-analysis-date", methods=["POST"])
@login_required
def update_analysis_date():
    if current_user.role != "admin":
        flash("Acesso restrito.", "danger")
        return redirect(url_for("management_panel"))
    
    start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d").date()
    uow = SqlAlchemyUnitOfWork()
    with uow:
        settings = uow.session.query(CompanySettings).first()
        if settings:
            settings.start_analysis_date = start_date
        else:
            settings = CompanySettings(lat=0, lon=0, start_analysis_date=start_date)
            uow.session.add(settings)
        uow.commit()
    
    flash("Data de inÃ­cio de anÃ¡lise atualizada.", "success")
    return redirect(url_for("management_panel"))


@app.route("/submit-correction", methods=["POST"])
@login_required
def submit_correction():
    try:
        ponto_date = datetime.strptime(request.form.get("ponto_date"), "%Y-%m-%d").date()
        stage = request.form.get("stage")
        proposed_time = datetime.strptime(request.form.get("proposed_time"), "%H:%M").time()
        justification = request.form.get("justification")
        
        uow = SqlAlchemyUnitOfWork()
        services.submit_correction_request(uow, current_user.id, ponto_date, stage, proposed_time, justification)
        flash("Pedido de correÃ§Ã£o enviado para anÃ¡lise.", "success")
    except Exception as e:
        flash(f"Erro ao enviar correÃ§Ã£o: {str(e)}", "danger")
    return redirect(url_for("dashboard"))

@app.route("/submit-justification", methods=["POST"])
@login_required
def submit_justification():
    entry_date_str = request.form.get("entry_date")
    justification = request.form.get("justification")
    
    if not entry_date_str or not justification:
        flash("Data e justificativa sÃ£o obrigatÃ³rias.", "warning")
        return redirect(url_for("dashboard"))
    
    try:
        entry_date = datetime.strptime(entry_date_str, "%Y-%m-%d").date()
        uow = SqlAlchemyUnitOfWork()
        services.submit_justification(uow, current_user.id, entry_date, justification)
        flash("Justificativa enviada com sucesso.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    
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
                flash("Registro nÃ£o encontrado.", "warning")
    except Exception as e:
        flash(f"Erro ao salvar nota: {str(e)}", "danger")
    return redirect(url_for("dashboard"))

@app.route("/manager/review-correction/<int:request_id>/<string:action>", methods=["POST"])
@login_required
def review_correction(request_id, action):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    approved = (action == "approve")
    uow = SqlAlchemyUnitOfWork()
    try:
        services.review_correction_request(uow, current_user.id, request_id, approved)
        flash("CorreÃ§Ã£o processada com sucesso.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    
    return redirect(url_for("management_panel"))

@app.route("/download-report/<int:user_id>")
@login_required
def download_report(user_id):
    if current_user.id != user_id and current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    excel_file = services.generate_excel_report(uow, user_id)
    
    filename = f"relatorio_horas_{user_id}_{date.today()}.xlsx"
    return send_file(
        excel_file,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/manager/view-logs/<int:employee_id>")
@login_required
def view_employee_logs(employee_id):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    with uow:
        employee = uow.users.get_user_by_id(employee_id)
        if not employee:
            flash("Funcionário nÃ£o encontrado.", "danger")
            return redirect(url_for("dashboard"))
        
        recent_entries = sorted(employee.time_entries, key=lambda x: x.entry_date, reverse=True)
        return render_template("view_employee_logs.html", employee=employee, recent_entries=recent_entries)

@app.route("/manager/fix-ponto/<int:employee_id>", methods=["GET", "POST"])
@login_required
def fix_ponto(employee_id):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
        return redirect(url_for("dashboard"))

    uow = SqlAlchemyUnitOfWork()
    if request.method == "POST":
        entry_date = datetime.strptime(request.form.get("entry_date"), "%Y-%m-%d").date()
        
        def parse_time(val):
            return datetime.strptime(val, "%H:%M").time() if val else None

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
        return redirect(url_for("dashboard"))

    with uow:
        employee = uow.users.get_user_by_id(employee_id)
        return render_template("fix_ponto.html", employee=employee, today=date.today())

@app.route("/manager/add-vacation/<int:employee_id>", methods=["POST"])
@login_required
def add_vacation(employee_id):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d").date()
    end_date = datetime.strptime(request.form.get("end_date"), "%Y-%m-%d").date()
    
    uow = SqlAlchemyUnitOfWork()
    services.add_vacation(uow, current_user.id, employee_id, start_date, end_date)
    flash("PerÃ­odo de fÃ©rias adicionado.", "success")
    return redirect(url_for("dashboard"))

@app.route("/manager/add-holiday", methods=["POST"])
@login_required
def add_holiday():
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
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
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    services.delete_user(uow, current_user.id, user_id)
    flash("UsuÃ¡rio excluÃ­do.", "warning")
    return redirect(url_for("dashboard"))

@app.route("/manager/set-schedule/<int:employee_id>", methods=["GET", "POST"])
@login_required
def set_schedule(employee_id):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
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
            if journey_id > 0:
                with uow:
                    j = services.get_journey_type(uow, journey_id)
                    if j:
                        arr, l_s, l_e, dep, tol, has_lunch = j.expected_arrival, j.expected_lunch_start, j.expected_lunch_end, j.expected_departure, j.tolerance_minutes, j.has_lunch_break
            else:
                arr = parse_time(form.arrival.data)
                l_s = parse_time(form.lunch_start.data)
                l_e = parse_time(form.lunch_end.data)
                dep = parse_time(form.departure.data)
                tol = int(form.tolerance.data)
                has_lunch = form.has_lunch_break.data

            services.set_work_schedule(uow, current_user.id, employee_id, arr, l_s, l_e, dep, tol, has_lunch_break=has_lunch)
            
            if journey_id == 0 and form.save_as_new.data:
                services.create_journey_type(uow, current_user.id, form.save_as_new.data, arr, l_s, l_e, dep, tol, has_lunch_break=has_lunch)
                flash(f"Template '{form.save_as_new.data}' salvo!", "info")

            flash("HorÃ¡rio de trabalho configurado.", "success")
            return redirect(url_for("management_panel"))
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
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
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
            has_lunch_break=form.has_lunch_break.data
        )
        flash("Tipo de Jornada criado.", "success")
        return redirect(url_for("management_panel"))
    
    with uow:
        journeys = services.list_journey_types(uow)
        return render_template("manage_journeys.html", form=form, journeys=journeys)

@app.route("/manager/get-journey/<int:journey_id>")
@login_required
def get_journey_json(journey_id):
    if current_user.role not in ["manager", "admin"]:
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
        "tolerance": j.tolerance_minutes
    }

@app.route("/manager/edit-journey/<int:journey_id>", methods=["GET", "POST"])
@login_required
def edit_journey(journey_id):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
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
                has_lunch_break=form.has_lunch_break.data
            )
            flash("Tipo de Jornada atualizado.", "success")
            return redirect(url_for("manage_journeys"))
        except Exception as e:
            flash(f"Erro: {str(e)}", "danger")

    with uow:
        j = services.get_journey_type(uow, journey_id)
        if not j:
            flash("Jornada nÃ£o encontrada.", "danger")
            return redirect(url_for("manage_journeys"))
        
        if not request.method == "POST":
            form.name.data = j.name
            form.has_lunch_break.data = j.has_lunch_break
            form.arrival.data = j.expected_arrival.strftime("%H:%M")
            form.lunch_start.data = j.expected_lunch_start.strftime("%H:%M") if j.expected_lunch_start else ""
            form.lunch_end.data = j.expected_lunch_end.strftime("%H:%M") if j.expected_lunch_end else ""
            form.departure.data = j.expected_departure.strftime("%H:%M")
            form.tolerance.data = str(j.tolerance_minutes)
        
        return render_template("edit_journey.html", form=form, journey=j)

@app.route("/manager/delete-journey/<int:journey_id>", methods=["POST"])
@login_required
def delete_journey(journey_id):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    services.delete_journey_type(uow, current_user.id, journey_id)
    flash("Tipo de Jornada excluÃ­do.", "warning")
    return redirect(url_for("manage_journeys"))

@app.route("/manager/generate-missing", methods=["POST"])
@login_required
def generate_missing():
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    target_date_str = request.form.get("target_date")
    if not target_date_str:
        flash("Data nÃ£o fornecida.", "warning")
        return redirect(url_for("dashboard"))
        
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    uow = SqlAlchemyUnitOfWork()
    services.generate_missing_logs(uow, current_user.id, target_date)
    flash(f"Faltas processadas para {target_date}.", "info")
    return redirect(url_for("dashboard"))

@app.route("/manager/justify-ponto/<int:employee_id>/<string:entry_date>", methods=["POST"])
@login_required
def justify_ponto(employee_id, entry_date):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
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
    if current_user.role != "admin":
        flash("Acesso restrito ao Administrador.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    with uow:
        logs = uow.session.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
        return render_template("audit_logs.html", audit_logs=logs)

@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def admin_settings():
    if current_user.role != "admin":
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
            flash("ConfiguraÃ§Ãµes atualizadas.", "success")
            return redirect(url_for("admin_settings"))
            
    with uow:
        settings = uow.session.query(CompanySettings).first()
        return render_template("admin_settings.html", settings=settings)

@app.route("/manager/delete-ponto/<int:employee_id>/<string:entry_date>", methods=["POST"])
@login_required
def delete_ponto(employee_id, entry_date):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso nÃ£o autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    e_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
    uow = SqlAlchemyUnitOfWork()
    services.delete_ponto_entry(uow, current_user.id, employee_id, e_date)
    flash("Registro de ponto excluÃ­do.", "warning")
    return redirect(url_for("view_employee_logs", employee_id=employee_id))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


