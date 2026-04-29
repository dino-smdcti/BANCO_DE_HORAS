from flask import Flask, render_template, redirect, url_for, flash, request, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from src.adapters.orm import start_mappers, metadata
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer import services
from src.entrypoints.forms import LoginForm, RegisterForm, ProfileForm, WorkScheduleForm, JourneyTypeForm
from src.domain.model import User, PontoStatus, JourneyType
from werkzeug.security import check_password_hash
from sqlalchemy import create_engine
from datetime import datetime, date

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class AuthenticatedUser(UserMixin):
    def __init__(self, user):
        self.id = user.user_id
        self.email = user.email
        self.role = user.role
        self.is_profile_complete = user.is_profile_complete

@login_manager.user_loader
def load_user(user_id):
    uow = SqlAlchemyUnitOfWork()
    with uow:
        user = uow.users.get_user_by_id(int(user_id))
        if user:
            return AuthenticatedUser(user)
    return None

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
                return redirect(url_for("dashboard"))
            flash("Invalid email or password", "danger")
    return render_template("login.html", form=form)

@app.route("/register", methods=["GET", "POST"])
@login_required
def register():
    if current_user.role != "manager":
        flash("Acesso restrito a gestores.", "danger")
        return redirect(url_for("dashboard"))
    
    form = RegisterForm()
    if form.validate_on_submit():
        uow = SqlAlchemyUnitOfWork()
        try:
            services.register_user(uow, form.email.data, form.password.data, form.role.data)
            flash("Registered successfully!", "success")
            return redirect(url_for("dashboard"))
        except ValueError as e:
            flash(str(e), "danger")
    return render_template("register.html", form=form)

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
        flash("Profile completed successfully!", "success")
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
            try:
                services.update_credentials(uow, current_user.id, email, password)
                flash("Perfil atualizado!", "success")
                return redirect(url_for("dashboard"))
            except ValueError as e:
                flash(str(e), "danger")
        return render_template("profile.html", user=user)

@app.route("/manager/promote/<int:user_id>", methods=["POST"])
@login_required
def promote_user(user_id):
    if current_user.role != "manager":
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
    
    uow = SqlAlchemyUnitOfWork()
    with uow:
        if current_user.role == "manager":
            employees = services.get_all_employees(uow)
            return render_template("manager_dashboard.html", employees=employees, today=date.today())
        
        user = uow.users.get_user_by_id(current_user.id)
        if not user:
             flash("User not found", "danger")
             return redirect(url_for("logout"))
             
        today_date = date.today()
        ponto_hoje = next((p for p in user.time_entries if p.entry_date == today_date), None)
        current_stage = ponto_hoje.current_stage if ponto_hoje else "Chegada"
        
        recent_entries = sorted(user.time_entries, key=lambda x: x.entry_date, reverse=True)[:10]
        
        maps_url = None
        if ponto_hoje and ponto_hoje.location_data:
            locs = ponto_hoje.location_data.split("|")
            last_loc = locs[-1].split(":")[-1].strip()
            maps_url = get_maps_url(last_loc)

        return render_template("employee_dashboard.html", 
                             recent_entries=recent_entries, 
                             current_stage=current_stage,
                             maps_url=maps_url)

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
    if current_user.role != "manager":
        flash("Unauthorized", "danger")
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
    if current_user.role != "manager":
        flash("Unauthorized", "danger")
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
            parse_time(request.form.get("departure"))
        )
        flash("Registro corrigido manualmente.", "success")
        return redirect(url_for("dashboard"))

    with uow:
        employee = uow.users.get_user_by_id(employee_id)
        return render_template("fix_ponto.html", employee=employee, today=date.today())

@app.route("/manager/add-vacation/<int:employee_id>", methods=["POST"])
@login_required
def add_vacation(employee_id):
    if current_user.role != "manager":
        flash("Unauthorized", "danger")
        return redirect(url_for("dashboard"))
    
    start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d").date()
    end_date = datetime.strptime(request.form.get("end_date"), "%Y-%m-%d").date()
    
    uow = SqlAlchemyUnitOfWork()
    services.add_vacation(uow, current_user.id, employee_id, start_date, end_date)
    flash("Vacation period added.", "success")
    return redirect(url_for("dashboard"))

@app.route("/manager/add-holiday", methods=["POST"])
@login_required
def add_holiday():
    if current_user.role != "manager":
        flash("Unauthorized", "danger")
        return redirect(url_for("dashboard"))
    
    h_date = datetime.strptime(request.form.get("holiday_date"), "%Y-%m-%d").date()
    desc = request.form.get("description")
    mandatory = request.form.get("is_mandatory") == "on"
    
    uow = SqlAlchemyUnitOfWork()
    services.add_holiday(uow, current_user.id, h_date, desc, mandatory)
    flash("Holiday added.", "success")
    return redirect(url_for("dashboard"))

@app.route("/manager/delete-user/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if current_user.role != "manager":
        flash("Unauthorized", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    services.delete_user(uow, current_user.id, user_id)
    flash("User deleted.", "warning")
    return redirect(url_for("dashboard"))

@app.route("/manager/set-schedule/<int:employee_id>", methods=["GET", "POST"])
@login_required
def set_schedule(employee_id):
    if current_user.role != "manager":
        flash("Unauthorized", "danger")
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
    if current_user.role != "manager":
        flash("Unauthorized", "danger")
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
        return redirect(url_for("manage_journeys"))
    
    with uow:
        journeys = services.list_journey_types(uow)
        return render_template("manage_journeys.html", form=form, journeys=journeys)

@app.route("/manager/get-journey/<int:journey_id>")
@login_required
def get_journey_json(journey_id):
    if current_user.role != "manager":
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
    if current_user.role != "manager":
        flash("Unauthorized", "danger")
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
    if current_user.role != "manager":
        flash("Unauthorized", "danger")
        return redirect(url_for("dashboard"))
    
    uow = SqlAlchemyUnitOfWork()
    services.delete_journey_type(uow, current_user.id, journey_id)
    flash("Tipo de Jornada excluído.", "warning")
    return redirect(url_for("manage_journeys"))

@app.route("/manager/generate-missing", methods=["POST"])
@login_required
def generate_missing():
    if current_user.role != "manager":
        flash("Unauthorized", "danger")
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
    if current_user.role != "manager":
        flash("Unauthorized", "danger")
        return redirect(url_for("dashboard"))
    
    justified = request.form.get("justified") == "true"
    e_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
    
    uow = SqlAlchemyUnitOfWork()
    try:
        services.justify_missing_log(uow, current_user.id, employee_id, e_date, justified)
        flash("Status atualizado.", "success")
    except ValueError as e:
        flash(str(e), "danger")
        
    return redirect(url_for("dashboard"))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

def init_db():
    engine = create_engine("sqlite:///banco_de_horas.db")
    metadata.create_all(engine)
    start_mappers()
    
    uow = SqlAlchemyUnitOfWork()
    with uow:
        any_user = uow.session.query(User).first()
        if not any_user:
            services.register_user(uow, "admin@admin.com", "admin123", role="manager")
            print("Primeiro usuário (ADMIN) criado: admin@admin.com / admin123")
