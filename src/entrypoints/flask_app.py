from flask import Flask, render_template, redirect, url_for, flash, request, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from src.adapters.orm import start_mappers, metadata
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer import services
from src.entrypoints.forms import LoginForm, RegisterForm, ProfileForm
from src.domain.model import User
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
    if current_user.role == "manager":
        employees = services.get_all_employees(uow)
        return render_template("manager_dashboard.html", employees=employees)
    
    with uow:
        user = uow.users.get_user_by_id(current_user.id)
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
