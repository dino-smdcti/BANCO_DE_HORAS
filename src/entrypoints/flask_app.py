from flask import Flask, render_template, redirect, url_for, flash, request, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from src.adapters.orm import start_mappers, metadata
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer import services
from src.entrypoints.forms import LoginForm, RegisterForm, ProfileForm, WorkScheduleForm, JourneyTypeForm
from src.domain.model import User, PontoStatus, JourneyType, AuditLog
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import create_engine
from datetime import datetime, date
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from itsdangerous import URLSafeTimedSerializer
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

database_url = os.environ.get("DATABASE_URL", "sqlite:///banco_de_horas.db")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url

app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")

# Initialize DB and Mappers
engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
metadata.create_all(engine)
try:
    start_mappers()
except Exception:
    # Mappers might already be started in some environments/tests
    pass

uow = SqlAlchemyUnitOfWork()
with uow:
    admin_user = uow.users.get_user_by_email("admin@admin.com")
    if not admin_user:
        admin_pw = os.environ.get("INITIAL_ADMIN_PASSWORD", "admin123")
        services.register_user(uow, "admin@admin.com", admin_pw, role="admin")
        print(f"Usuário ADMIN criado: admin@admin.com / {admin_pw}")

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
        self.has_schedule = user.work_schedule is not None

@login_manager.user_loader
def load_user(user_id):
    uow = SqlAlchemyUnitOfWork()
    with uow:
        user = uow.users.get_user_by_id(int(user_id))
        if user:
            return AuthenticatedUser(user)
    return None

@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        uow = SqlAlchemyUnitOfWork()
        with uow:
            user = uow.users.get_user_by_id(current_user.id)
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
    return {"user_notifs": [], "user_notifs_count": 0}

def send_email(to_email, subject, body_html):
    msg = MIMEMultipart()
    msg["From"] = f"Banco de Horas <{app.config['MAIL_USERNAME']}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    
    msg.attach(MIMEText(body_html, "html"))
    
    try:
        server = smtplib.SMTP(app.config["MAIL_SERVER"], app.config["MAIL_PORT"])
        server.starttls()
        server.login(app.config["MAIL_USERNAME"], app.config["MAIL_PASSWORD"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
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
            services.register_user(uow, form.email.data, role=form.role.data)
            
            # Send invitation email
            token = serializer.dumps(form.email.data, salt="password-reset-salt")
            setup_url = url_for("reset_password", token=token, _external=True)
            html = render_template("emails/welcome_invite.html", setup_url=setup_url)
            if send_email(form.email.data, "Bem-vindo ao Banco de Horas - Ative sua conta", html):
                flash("Usuário cadastrado! Um convite foi enviado por e-mail.", "success")
            else:
                flash("Usuário cadastrado, mas houve um erro ao enviar o e-mail de convite. Verifique as configurações de SMTP.", "warning")
            
            return redirect(url_for("dashboard"))
        except ValueError as e:
            msg = str(e)
            if "already exists" in msg:
                msg = f"O usuário com e-mail {form.email.data} já está cadastrado."
            flash(msg, "danger")
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
    if current_user.role not in ["manager", "admin"]:
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
    if current_user.role not in ["manager", "admin"]:
        flash("Não autorizado", "danger")
        return redirect(url_for("dashboard"))
    uow = SqlAlchemyUnitOfWork()
    services.promote_to_manager(uow, current_user.id, user_id)
    flash("Usuário promovido a Gestor!", "success")
    return redirect(url_for("dashboard"))

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
        ponto_hoje = next((p for p in user.time_entries if p.entry_date == today_date), None)
        current_stage = ponto_hoje.current_stage if ponto_hoje else "Chegada"
        
        if filter_date:
            recent_entries = [p for p in user.time_entries if p.entry_date == filter_date]
        else:
            recent_entries = sorted(user.time_entries, key=lambda x: x.entry_date, reverse=True)[:10]
        
        # Calculate balances
        if user.work_schedule:
            def delta(t1, t2):
                return int((datetime.combine(date.min, t2) - datetime.combine(date.min, t1)).total_seconds() / 60)
            
            expected_daily = (delta(user.work_schedule.expected_arrival, user.work_schedule.expected_lunch_start) + 
                              delta(user.work_schedule.expected_lunch_end, user.work_schedule.expected_departure))
            
            saldo_total = user.total_balance
            
            if ponto_hoje:
                saldo_dia = ponto_hoje.worked_minutes - expected_daily
            else:
                saldo_dia = 0
        else:
            saldo_total = 0
            saldo_dia = 0

        maps_url = None
        if ponto_hoje and ponto_hoje.location_data:
            locs = ponto_hoje.location_data.split("|")
            last_loc = locs[-1].split(":")[-1].strip()
            maps_url = get_maps_url(last_loc)

        return render_template("employee_dashboard.html", 
                             recent_entries=recent_entries, 
                             current_stage=current_stage,
                             maps_url=maps_url,
                             filter_date=filter_date_str,
                             saldo_dia=saldo_dia,
                             saldo_total=saldo_total)

@app.route("/management")
@login_required
def management_panel():
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso restrito.", "danger")
        return redirect(url_for("dashboard"))
        
    uow = SqlAlchemyUnitOfWork()
    with uow:
        employees = services.get_all_employees(uow)
        return render_template("manager_dashboard.html", employees=employees, today=date.today())


@app.route("/submit-justification", methods=["POST"])
@login_required
def submit_justification():
    entry_date_str = request.form.get("entry_date")
    justification = request.form.get("justification")
    
    if not entry_date_str or not justification:
        flash("Data e justificativa são obrigatórias.", "warning")
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
    uow = SqlAlchemyUnitOfWork()
    try:
        msg = services.clock_in_out(uow, current_user.id, location)
        flash(msg, "info")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("dashboard"))

@app.route("/download-report/<int:user_id>")
@login_required
def download_report(user_id):
    if current_user.id != user_id and current_user.role != "manager":
        flash("Acesso não autorizado.", "danger")
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
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    with uow:
        employee = uow.users.get_user_by_id(employee_id)
        if not employee:
            flash("Funcionário não encontrado.", "danger")
            return redirect(url_for("dashboard"))
        
        recent_entries = sorted(employee.time_entries, key=lambda x: x.entry_date, reverse=True)
        return render_template("view_employee_logs.html", employee=employee, recent_entries=recent_entries)

@app.route("/manager/fix-ponto/<int:employee_id>", methods=["GET", "POST"])
@login_required
def fix_ponto(employee_id):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso não autorizado.", "danger")
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
    if current_user.role not in ["manager", "admin"]:
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
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    services.delete_user(uow, current_user.id, user_id)
    flash("Usuário excluído.", "warning")
    return redirect(url_for("dashboard"))

@app.route("/manager/set-schedule/<int:employee_id>", methods=["GET", "POST"])
@login_required
def set_schedule(employee_id):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))

    uow = SqlAlchemyUnitOfWork()
    form = WorkScheduleForm()
    
    with uow:
        journeys = services.list_journey_types(uow)
        form.journey_type.choices = [(0, "Selecione um template...")] + [(j.journey_id, j.name) for j in journeys]

    if form.validate_on_submit():
        def parse_time(val):
            return datetime.strptime(val, "%H:%M").time()

        try:
            arr = parse_time(form.arrival.data)
            l_s = parse_time(form.lunch_start.data)
            l_e = parse_time(form.lunch_end.data)
            dep = parse_time(form.departure.data)
            tol = int(form.tolerance.data)

            services.set_work_schedule(uow, current_user.id, employee_id, arr, l_s, l_e, dep, tol)
            
            if form.save_as_new.data:
                services.create_journey_type(uow, current_user.id, form.save_as_new.data, arr, l_s, l_e, dep, tol)
                flash(f"Template '{form.save_as_new.data}' salvo!", "info")

            flash("Horário de trabalho configurado.", "success")
            return redirect(url_for("dashboard"))
        except Exception as e:
            flash(f"Erro: {str(e)}", "danger")

    with uow:
        employee = uow.users.get_user_by_id(employee_id)
        if not request.method == "POST" and employee.work_schedule:
            form.arrival.data = employee.work_schedule.expected_arrival.strftime("%H:%M")
            form.lunch_start.data = employee.work_schedule.expected_lunch_start.strftime("%H:%M")
            form.lunch_end.data = employee.work_schedule.expected_lunch_end.strftime("%H:%M")
            form.departure.data = employee.work_schedule.expected_departure.strftime("%H:%M")
            form.tolerance.data = str(employee.work_schedule.tolerance_minutes)
        
        journeys = services.list_journey_types(uow)
        return render_template("set_schedule.html", form=form, employee=employee, journeys=journeys)

@app.route("/manager/journey-types", methods=["GET", "POST"])
@login_required
def manage_journeys():
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    form = JourneyTypeForm()
    
    if form.validate_on_submit():
        def parse_time(val):
            return datetime.strptime(val, "%H:%M").time()
        
        services.create_journey_type(
            uow, current_user.id, form.name.data,
            parse_time(form.arrival.data),
            parse_time(form.lunch_start.data),
            parse_time(form.lunch_end.data),
            parse_time(form.departure.data),
            int(form.tolerance.data)
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
        "lunch_start": j.expected_lunch_start.strftime("%H:%M"),
        "lunch_end": j.expected_lunch_end.strftime("%H:%M"),
        "departure": j.expected_departure.strftime("%H:%M"),
        "tolerance": j.tolerance_minutes
    }

@app.route("/manager/edit-journey/<int:journey_id>", methods=["GET", "POST"])
@login_required
def edit_journey(journey_id):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    form = JourneyTypeForm()
    
    if form.validate_on_submit():
        def parse_time(val):
            return datetime.strptime(val, "%H:%M").time()
        
        try:
            services.update_journey_type(
                uow, current_user.id, journey_id, form.name.data,
                parse_time(form.arrival.data),
                parse_time(form.lunch_start.data),
                parse_time(form.lunch_end.data),
                parse_time(form.departure.data),
                int(form.tolerance.data)
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
            form.arrival.data = j.expected_arrival.strftime("%H:%M")
            form.lunch_start.data = j.expected_lunch_start.strftime("%H:%M")
            form.lunch_end.data = j.expected_lunch_end.strftime("%H:%M")
            form.departure.data = j.expected_departure.strftime("%H:%M")
            form.tolerance.data = str(j.tolerance_minutes)
        
        return render_template("edit_journey.html", form=form, journey=j)

@app.route("/manager/delete-journey/<int:journey_id>", methods=["POST"])
@login_required
def delete_journey(journey_id):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    services.delete_journey_type(uow, current_user.id, journey_id)
    flash("Tipo de Jornada excluído.", "warning")
    return redirect(url_for("manage_journeys"))

@app.route("/manager/generate-missing", methods=["POST"])
@login_required
def generate_missing():
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    target_date_str = request.form.get("target_date")
    if not target_date_str:
        flash("Data não fornecida.", "warning")
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
        flash("Acesso não autorizado.", "danger")
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

@app.route("/manager/delete-ponto/<int:employee_id>/<string:entry_date>", methods=["POST"])
@login_required
def delete_ponto(employee_id, entry_date):
    if current_user.role not in ["manager", "admin"]:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for("dashboard"))
    
    e_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
    uow = SqlAlchemyUnitOfWork()
    services.delete_ponto_entry(uow, current_user.id, employee_id, e_date)
    flash("Registro de ponto excluído.", "warning")
    return redirect(url_for("view_employee_logs", employee_id=employee_id))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))
