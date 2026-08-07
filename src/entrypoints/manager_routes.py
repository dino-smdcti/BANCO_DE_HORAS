from collections import namedtuple
from datetime import date, datetime

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from src.domain.model import JourneyType, PontoStatus, UserProfile, UserRole
from src.entrypoints import flask_app
from src.entrypoints.decorators import handle_errors, manager_required
from src.entrypoints.forms import JourneyTypeForm, ProfileForm, RegisterForm, WorkScheduleForm
from src.entrypoints.web_helpers import INVALID_DATE, is_management_role, new_uow, parse_date, parse_time
from src.service_layer import services
from src.service_layer.audit import log_action

_ScheduleValues = namedtuple("_ScheduleValues", ["arrival", "lunch_start", "lunch_end", "departure", "tolerance", "has_lunch_break", "schedule_type"])


def register_routes(app):
        app.add_url_rule("/register", "register", register, methods=["GET", "POST"])
        app.add_url_rule("/manager/edit-employee/<int:employee_id>", "edit_employee", edit_employee, methods=["GET", "POST"])
        app.add_url_rule("/manager/promote/<int:user_id>", "promote_user", promote_user, methods=["POST"])
        app.add_url_rule("/manager/change-role/<int:user_id>", "change_user_role", change_user_role, methods=["POST"])
        app.add_url_rule("/manager/demote/<int:user_id>", "demote_user", demote_user, methods=["POST"])
        app.add_url_rule("/manager/archive-justification/<int:employee_id>/<string:entry_date>", "archive_justification", archive_justification, methods=["POST"])
        app.add_url_rule("/manager/archived-justifications", "archived_justifications", archived_justifications)
        app.add_url_rule("/manager/archive-justification-action/<int:employee_id>/<string:entry_date>", "archive_justification_action", archive_justification_action, methods=["POST"])
        app.add_url_rule("/management", "management_panel", management_panel)
        app.add_url_rule("/admin/update-user-analysis-date/<int:employee_id>", "update_user_analysis_date", update_user_analysis_date, methods=["POST"])
        app.add_url_rule("/manager/review-correction/<int:request_id>/<string:action>", "review_correction", review_correction, methods=["POST"])
        app.add_url_rule("/manager/view-logs/<int:employee_id>", "view_employee_logs", view_employee_logs)
        app.add_url_rule("/manager/bulk-fix-ponto/<int:employee_id>", "bulk_fix_ponto", bulk_fix_ponto, methods=["POST"])
        app.add_url_rule("/manager/fix-ponto/<int:employee_id>", "fix_ponto", fix_ponto, methods=["GET", "POST"])
        app.add_url_rule("/manager/add-vacation/<int:employee_id>", "add_vacation", add_vacation, methods=["POST"])
        app.add_url_rule("/manager/add-attestation/<int:employee_id>", "add_attestation", add_attestation, methods=["POST"])
        app.add_url_rule("/manager/add-holiday", "add_holiday", add_holiday, methods=["POST"])
        app.add_url_rule("/manager/add-facultativo", "add_facultativo", add_facultativo, methods=["POST"])
        app.add_url_rule("/manager/delete-user/<int:user_id>", "delete_user", delete_user, methods=["POST"])
        app.add_url_rule("/manager/reset-user-password/<int:user_id>", "reset_user_password", reset_user_password, methods=["POST"])
        app.add_url_rule("/manager/set-schedule/<int:employee_id>", "set_schedule", set_schedule, methods=["GET", "POST"])
        app.add_url_rule("/manager/journey-types", "manage_journeys", manage_journeys, methods=["GET", "POST"])
        app.add_url_rule("/manager/get-journey/<int:journey_id>", "get_journey_json", get_journey_json)
        app.add_url_rule("/manager/edit-journey/<int:journey_id>", "edit_journey", edit_journey, methods=["GET", "POST"])
        app.add_url_rule("/manager/delete-journey/<int:journey_id>", "delete_journey", delete_journey, methods=["POST"])
        app.add_url_rule("/manager/delete-ponto/<int:employee_id>/<string:entry_date>", "delete_ponto", delete_ponto, methods=["POST"])
        app.add_url_rule("/manager/review-badge/<int:employee_id>/<string:entry_date>/<string:stage>/<string:action>", "review_badge", review_badge, methods=["POST"])
        app.add_url_rule("/manager/save-manager-note", "save_manager_note", save_manager_note, methods=["POST"])


@login_required
@manager_required
@handle_errors
def register():
        form = RegisterForm()
        if form.validate_on_submit():
                return _handle_register(form)
        return render_template("register.html", form=form)


@login_required
def edit_employee(employee_id):
        denied = _role_guard()
        if denied:
                return denied
        form = ProfileForm()
        uow = new_uow()
        with uow:
                return _render_edit_employee(uow, employee_id, form)


@login_required
def promote_user(user_id):
        if current_user.role != "admin":
                flash("Acesso não autorizado", "danger")
                return redirect(url_for("dashboard"))
        uow = new_uow()
        services.promote_to_manager(uow, current_user.id, user_id)
        flash("Usuário promovido a Gestor!", "success")
        return redirect(url_for("management_panel"))


@login_required
def change_user_role(user_id):
        if not is_management_role(current_user.role):
                return {"success": False, "message": "Acesso não autorizado"}, 403
        new_role = request.json.get("role")
        if new_role not in ["employee", "gestor", "manager", "admin"]:
                return {"success": False, "message": "Perfil inválido"}, 400
        uow = new_uow()
        with uow:
                return _change_role_response(uow, user_id, new_role)


@login_required
def demote_user(user_id):
        if current_user.role != "admin":
                flash("Acesso não autorizado", "danger")
                return redirect(url_for("dashboard"))
        uow = new_uow()
        services.demote_to_employee(uow, current_user.id, user_id)
        flash("Usuário rebaixado para Funcionário!", "warning")
        return redirect(url_for("management_panel"))


@login_required
@manager_required
@handle_errors
def archive_justification(employee_id, entry_date):
        return _archive_justification(employee_id, entry_date)


@login_required
@manager_required
@handle_errors
def archived_justifications():
        uow = new_uow()
        with uow:
                return _render_archived(uow)


@login_required
@manager_required
@handle_errors
def archive_justification_action(employee_id, entry_date):
        return _archive_justification(employee_id, entry_date)


@login_required
def management_panel():
        denied = _role_guard(message="Acesso restrito.")
        if denied:
                return denied
        uow = new_uow()
        with uow:
                return _render_management_panel(uow)


@login_required
def update_user_analysis_date(employee_id):
        denied = _role_guard()
        if denied:
                return denied
        start_date = datetime.strptime(request.form.get("start_analysis_date"), "%Y-%m-%d").date()
        uow = new_uow()
        with uow:
                _apply_analysis_date(uow, employee_id, start_date)
        return redirect(url_for("view_employee_logs", employee_id=employee_id))


@login_required
def review_correction(request_id, action):
        denied = _role_guard()
        if denied:
                return denied
        uow = new_uow()
        try:
                services.review_correction_request(uow, current_user.id, request_id, action == "approve")
                flash("Correção processada com sucesso.", "success")
        except ValueError as error:
                flash(str(error), "danger")
        return redirect(url_for("management_panel"))


@login_required
def view_employee_logs(employee_id):
        denied = _role_guard()
        if denied:
                return denied
        uow = new_uow()
        with uow:
                return _render_employee_logs(uow, employee_id)


@login_required
def bulk_fix_ponto(employee_id):
        denied = _role_guard()
        if denied:
                return denied
        uow = new_uow()
        try:
                _apply_bulk_fixes(uow, employee_id)
                flash("Registros selecionados atualizados com sucesso.", "success")
        except Exception as error:
                flash(f"Erro ao processar correções: {str(error)}", "danger")
        return _bulk_redirect(employee_id)


@login_required
def fix_ponto(employee_id):
        denied = _role_guard()
        if denied:
                return denied
        uow = new_uow()
        if request.method == "POST":
                _apply_fix(uow, employee_id)
                flash("Registro corrigido manualmente.", "success")
                return redirect(url_for("view_employee_logs", employee_id=employee_id))
        with uow:
                employee = uow.users.get_user_by_id(employee_id)
                return render_template("fix_ponto.html", employee=employee, today=date.today())


@login_required
def add_vacation(employee_id):
        denied = _role_guard()
        if denied:
                return denied
        start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d").date()
        end_date = datetime.strptime(request.form.get("end_date"), "%Y-%m-%d").date()
        uow = new_uow()
        services.add_vacation(uow, current_user.id, employee_id, start_date, end_date)
        flash("Período de férias adicionado.", "success")
        return redirect(url_for("dashboard"))


@login_required
def add_attestation(employee_id):
        denied = _role_guard()
        if denied:
                return denied
        start_date = parse_date(request.form.get("start_date"))
        end_date = parse_date(request.form.get("end_date"))
        cid = (request.form.get("cid") or "").strip()
        start_time = parse_time(request.form.get("start_time"))
        end_time = parse_time(request.form.get("end_time"))
        if start_date is None or end_date is None or start_date is INVALID_DATE or end_date is INVALID_DATE:
                flash("Informe o período do atestado.", "danger")
                return redirect(url_for("view_employee_logs", employee_id=employee_id))
        uow = new_uow()
        try:
                services.add_attestation(uow, current_user.id, employee_id, start_date, end_date, cid or None, start_time, end_time)
        except ValueError as error:
                flash(str(error), "danger")
                return redirect(url_for("view_employee_logs", employee_id=employee_id))
        flash("Atestado lançado com sucesso.", "success")
        return redirect(url_for("view_employee_logs", employee_id=employee_id))


@login_required
def add_holiday():
        denied = _role_guard()
        if denied:
                return denied
        holiday_date = datetime.strptime(request.form.get("holiday_date"), "%Y-%m-%d").date()
        description = request.form.get("description")
        mandatory = request.form.get("is_mandatory") == "on"
        uow = new_uow()
        services.add_holiday(uow, current_user.id, holiday_date, description, mandatory)
        flash("Feriado adicionado.", "success")
        return redirect(url_for("dashboard"))


@login_required
def add_facultativo():
        denied = _role_guard()
        if denied:
                return denied
        start_date = parse_date(request.form.get("start_date"))
        end_date = parse_date(request.form.get("end_date"))
        description = (request.form.get("description") or "").strip()
        start_time = parse_time(request.form.get("start_time"))
        end_time = parse_time(request.form.get("end_time"))
        if start_date is None or end_date is None or start_date is INVALID_DATE or end_date is INVALID_DATE:
                flash("Informe o período do ponto facultativo.", "danger")
                return redirect(url_for("management_panel"))
        uow = new_uow()
        try:
                services.add_facultativo(uow, current_user.id, start_date, end_date, description, start_time, end_time)
        except ValueError as error:
                flash(str(error), "danger")
                return redirect(url_for("management_panel"))
        flash("Ponto facultativo lançado.", "success")
        return redirect(url_for("management_panel"))


@login_required
def delete_user(user_id):
        denied = _role_guard()
        if denied:
                return denied
        uow = new_uow()
        services.delete_user(uow, current_user.id, user_id)
        flash("Usuário excluído.", "warning")
        return redirect(url_for("management_panel"))


@login_required
def reset_user_password(user_id):
        denied = _role_guard()
        if denied:
                return denied
        uow = new_uow()
        with uow:
                return _send_password_reset(uow, user_id)


@login_required
def set_schedule(employee_id):
        denied = _role_guard()
        if denied:
                return denied
        uow = new_uow()
        form = WorkScheduleForm()
        _load_journey_choices(uow, form)
        if form.validate_on_submit():
                response = _apply_schedule_form(uow, employee_id, form)
                if response:
                        return response
        with uow:
                employee = uow.users.get_user_by_id(employee_id)
                _prefill_schedule_form(form, employee)
                journeys = services.list_journey_types(uow)
                return render_template("set_schedule.html", form=form, employee=employee, journeys=journeys)


@login_required
def manage_journeys():
        denied = _role_guard()
        if denied:
                return denied
        uow = new_uow()
        form = JourneyTypeForm()
        if form.validate_on_submit():
                _create_journey_from_form(uow, form)
                flash("Tipo de Jornada criado.", "success")
                return redirect(url_for("management_panel"))
        with uow:
                journeys = services.list_journey_types(uow)
                return render_template("manage_journeys.html", form=form, journeys=journeys)


@login_required
def get_journey_json(journey_id):
        if not is_management_role(current_user.role):
                return {"error": "Unauthorized"}, 403
        uow = new_uow()
        with uow:
                journey = uow.session.execute(select(JourneyType).where(JourneyType.journey_id == journey_id)).scalar_one_or_none()
                if not journey:
                        return {"error": "Not found"}, 404
                return _journey_payload(journey)


@login_required
def edit_journey(journey_id):
        denied = _role_guard()
        if denied:
                return denied
        uow = new_uow()
        form = JourneyTypeForm()
        if form.validate_on_submit():
                response = _update_journey_from_form(uow, journey_id, form)
                if response:
                        return response
        with uow:
                journey = services.get_journey_type(uow, journey_id)
                if not journey:
                        flash("Jornada não encontrada.", "danger")
                        return redirect(url_for("manage_journeys"))
                if request.method != "POST":
                        _prefill_journey_form(form, journey)
                return render_template("edit_journey.html", form=form, journey=journey)


@login_required
def delete_journey(journey_id):
        denied = _role_guard()
        if denied:
                return denied
        uow = new_uow()
        services.delete_journey_type(uow, current_user.id, journey_id)
        flash("Tipo de Jornada excluído.", "warning")
        return redirect(url_for("manage_journeys"))


@login_required
def delete_ponto(employee_id, entry_date):
        denied = _role_guard()
        if denied:
                return denied
        entry_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
        uow = new_uow()
        services.delete_ponto_entry(uow, current_user.id, employee_id, entry_date)
        flash("Registro de ponto excluído.", "warning")
        return _ponto_redirect(employee_id)


@login_required
def review_badge(employee_id, entry_date, stage, action):
        if current_user.role not in ["admin", "gestor"]:
                flash("Apenas o Administrador pode realizar esta ação.", "danger")
                return redirect(url_for("view_employee_logs", employee_id=employee_id))
        entry_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
        uow = new_uow()
        try:
                services.review_anomaly_badge(uow, int(current_user.id), employee_id, entry_date, stage, action)
                flash("Badge de anomalia atualizado com sucesso.", "success")
        except Exception as error:
                flash(str(error), "danger")
        return redirect(url_for("view_employee_logs", employee_id=employee_id))


@login_required
@manager_required
@handle_errors
def save_manager_note():
        employee_id = int(request.form.get("employee_id"))
        entry_date = datetime.strptime(request.form.get("entry_date"), "%Y-%m-%d").date()
        note_text = request.form.get("note_text")
        uow = new_uow()
        with uow:
                user = uow.users.get_user_by_id(employee_id)
                ponto = next((entry for entry in user.time_entries if entry.entry_date == entry_date), None)
                if not ponto:
                        return {"status": "error", "message": "Registro não encontrado."}, 404
                services.manual_ponto_correction(
                        uow, current_user.id, employee_id, entry_date,
                        ponto.arrival, ponto.lunch_start, ponto.lunch_end, ponto.departure,
                        manager_notes=note_text,
                )
        return {"status": "success"}


def _role_guard(message="Acesso não autorizado."):
        """Redirect non-management users back to their dashboard."""
        if not is_management_role(current_user.role):
                flash(message, "danger")
                return redirect(url_for("dashboard"))
        return None


def _handle_register(form):
        try:
                is_new = _register_or_none(form)
                return _send_invitation(form, is_new)
        except Exception as error:
                flash(f"Erro ao cadastrar usuário: {str(error)}", "danger")
                return render_template("register.html", form=form)


def _register_or_none(form):
        uow = new_uow()
        try:
                services.register_user(uow, form.email.data, role=form.role.data, registered_by_id=current_user.id)
                return True
        except ValueError as error:
                if "already exists" in str(error).lower():
                        return False
                raise


def _send_invitation(form, is_new):
        token = flask_app.serializer.dumps(form.email.data, salt="password-reset-salt")
        setup_url = url_for("reset_password", token=token, _external=True)
        html = render_template("emails/welcome_invite.html", setup_url=setup_url)
        if flask_app.send_email(form.email.data, "Bem-vindo ao Banco de Horas - Ative sua conta", html):
                if is_new:
                        flash("Usuário cadastrado! Um convite foi enviado por e-mail.", "success")
                else:
                        flash("O usuário já estava cadastrado. O convite foi reenviado com sucesso.", "info")
        else:
                status_msg = "Usuário cadastrado, mas o e-mail falhou. " if is_new else "O usuário já existe, mas o e-mail falhou. "
                flash(f"{status_msg} Copie o link de ativação: {setup_url}", "warning")
        return redirect(url_for("dashboard"))


def _render_edit_employee(uow, employee_id, form):
        employee = uow.users.get_user_by_id(employee_id)
        if not employee:
                flash("Funcionário não encontrado.", "danger")
                return redirect(url_for("management_panel"))
        if form.validate_on_submit():
                _save_employee_profile(uow, employee_id, form)
                flash(f"Perfil de {employee.profile.full_name or employee.email} atualizado!", "success")
                return redirect(url_for("management_panel"))
        if request.method != "POST":
                _populate_employee_form(form, employee)
        return render_template("complete_profile.html", form=form, title=f"Editar Perfil: {employee.email}")


def _save_employee_profile(uow, employee_id, form):
        services.update_user_profile(
                uow, employee_id,
                form.registration_number.data,
                form.cpf.data,
                form.department.data,
                form.position.data,
                form.secretariat.data,
                form.full_name.data,
                birth_date=form.birth_date.data,
        )


def _populate_employee_form(form, employee):
        form.registration_number.data = employee.profile.registration_number
        form.cpf.data = employee.profile.cpf
        form.department.data = employee.profile.department
        form.position.data = employee.profile.position
        form.secretariat.data = employee.profile.secretariat
        form.full_name.data = employee.profile.full_name
        form.birth_date.data = employee.profile.birth_date


def _change_role_response(uow, user_id, new_role):
        employee = uow.users.get_user_by_id(user_id)
        if not employee:
                return {"success": False, "message": "Usuário não encontrado"}, 404
        old_role = employee.role.value if hasattr(employee.role, "value") else employee.role
        employee.role = UserRole(new_role)
        action = "PROMOTE_USER" if new_role in ["gestor", "manager", "admin"] else "DEMOTE_USER"
        log_action(uow, current_user.id, action, target_id=user_id, details=f"Perfil alterado de {old_role} para {new_role}")
        return {"success": True, "message": "Perfil atualizado com sucesso!"}


def _archive_justification(employee_id, entry_date):
        entry_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
        uow = new_uow()
        services.dismiss_justification(uow, current_user.id, employee_id, entry_date)
        flash("Justificativa arquivada com sucesso.", "info")
        return redirect(url_for("management_panel"))


def _render_archived(uow):
        employees = services.get_all_employees(uow, requester_id=int(current_user.id))
        archived = _dismissed_entries(employees)
        employee_id = request.args.get("employee_id")
        if employee_id:
                archived = [entry for entry in archived if entry["emp"].user_id == int(employee_id)]
        date_str = request.args.get("date")
        if date_str:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                archived = [entry for entry in archived if entry["ponto"].entry_date == target_date]
        return render_template(
                "archived_justifications.html",
                archived_justs=archived,
                employees=employees,
                selected_emp=int(employee_id) if employee_id else None,
                selected_date=date_str,
        )


def _render_management_panel(uow):
        employees = services.get_all_employees(uow, requester_id=int(current_user.id))
        _refresh_all(uow, employees)
        return render_template(
                "manager_dashboard.html",
                employees=employees,
                today=date.today(),
                analysis_date=services.get_start_analysis_date(uow),
                absences=_absences(employees),
                dismissed_justs=_dismissed_entries(employees),
                pending_corrections=_corrections_display(uow),
                holidays=_holidays_serialized(uow),
        )


def _refresh_all(uow, employees):
        for employee in employees:
                uow.session.refresh(employee)


def _absences(employees):
        result = [{"emp": employee, "ponto": entry} for employee in employees for entry in employee.time_entries if _shows_on_absences_card(entry)]
        emp_filter = request.args.get("emp_filter")
        if emp_filter:
                result = [item for item in result if item["emp"].user_id == int(emp_filter)]
        date_filter = request.args.get("date_filter")
        if date_filter:
                target = datetime.strptime(date_filter, "%Y-%m-%d").date()
                result = [item for item in result if item["ponto"].entry_date == target]
        return result


def _shows_on_absences_card(entry):
        if entry.status in (PontoStatus.DISMISSED, PontoStatus.CORRECTED):
                return False
        return entry.status == PontoStatus.MISSING or bool(entry.notes)


def _dismissed_entries(employees):
        return [{"emp": employee, "ponto": entry} for employee in employees for entry in employee.time_entries if entry.status == PontoStatus.DISMISSED]


def _corrections_display(uow):
        pending = services.list_pending_corrections(uow, int(current_user.id))
        return [_correction_row(uow, request) for request in pending]


def _correction_row(uow, request):
        user = uow.users.get_user_by_id(request.user_id)
        return {
                "id": request.request_id,
                "user_name": user.profile.full_name or user.email,
                "date": request.ponto_date,
                "stage": request.stage,
                "time": request.proposed_time,
        }


def _holidays_serialized(uow):
        from src.domain.model import Holiday
        holidays = uow.session.execute(select(Holiday).order_by(Holiday.holiday_date)).scalars().all()
        return [{"date": holiday.holiday_date.strftime("%Y-%m-%d"), "description": holiday.description} for holiday in holidays]


def _apply_analysis_date(uow, employee_id, start_date):
        employee = uow.users.get_user_by_id(employee_id)
        if employee:
                employee.profile = UserProfile(
                        registration_number=employee.profile.registration_number,
                        cpf=employee.profile.cpf,
                        department=employee.profile.department,
                        position=employee.profile.position,
                        secretariat=employee.profile.secretariat,
                        full_name=employee.profile.full_name,
                        start_analysis_date=start_date,
                )
                uow.commit()
                flash(f"Data de início de análise de {employee.profile.full_name or employee.email} atualizada.", "success")
        else:
                flash("Funcionário não encontrado.", "danger")


def _render_employee_logs(uow, employee_id):
        employee = uow.users.get_user_by_id(employee_id)
        if not employee:
                flash("Funcionário não encontrado.", "danger")
                return redirect(url_for("dashboard"))
        uow.session.refresh(employee)
        recent_entries = sorted(employee.time_entries, key=lambda entry: entry.entry_date, reverse=True)
        attestations = sorted(employee.attestations, key=lambda att: att.start_date, reverse=True)
        return render_template("view_employee_logs.html", employee=employee, recent_entries=recent_entries, attestations=attestations)


def _apply_bulk_fixes(uow, employee_id):
        dates = request.form.getlist("dates")
        emp_ids = request.form.getlist("emp_ids")
        selected_points = request.form.getlist("selected_points")
        if emp_ids and len(emp_ids) == len(dates):
                for index, entry_date_str in enumerate(dates):
                        _fix_emp_entry(uow, emp_ids[index], entry_date_str, selected_points, prefix_fields=True)
        else:
                for entry_date_str in dates:
                        _fix_emp_entry(uow, employee_id, entry_date_str, selected_points, prefix_fields=False)


def _fix_emp_entry(uow, employee_id, entry_date_str, selected_points, prefix_fields):
        key = f"{employee_id}_{entry_date_str}" if prefix_fields else entry_date_str
        if key not in selected_points:
                return
        entry_date = datetime.strptime(entry_date_str, "%Y-%m-%d").date()
        form_key = f"{employee_id}_{entry_date_str}" if prefix_fields else entry_date_str
        services.manual_ponto_correction(
                uow,
                current_user.id,
                int(employee_id),
                entry_date,
                parse_time(request.form.get(f"arrival_{form_key}")),
                parse_time(request.form.get(f"lunch_start_{form_key}")),
                parse_time(request.form.get(f"lunch_end_{form_key}")),
                parse_time(request.form.get(f"departure_{form_key}")),
                manager_notes=request.form.get(f"manager_notes_{entry_date_str}"),
        )


def _bulk_redirect(employee_id):
        if employee_id != 0:
                return redirect(url_for("view_employee_logs", employee_id=employee_id))
        return redirect(url_for("management_panel"))


def _ponto_redirect(employee_id):
        referrer = request.referrer or ""
        if "management" in referrer:
                return redirect(url_for("management_panel"))
        return redirect(url_for("view_employee_logs", employee_id=employee_id))


def _apply_fix(uow, employee_id):
        entry_date = datetime.strptime(request.form.get("entry_date"), "%Y-%m-%d").date()
        services.manual_ponto_correction(
                uow,
                current_user.id,
                employee_id,
                entry_date,
                parse_time(request.form.get("arrival")),
                parse_time(request.form.get("lunch_start")),
                parse_time(request.form.get("lunch_end")),
                parse_time(request.form.get("departure")),
                email_sender=flask_app.send_email,
        )


def _send_password_reset(uow, user_id):
        user = uow.users.get_user_by_id(user_id)
        if not user:
                flash("Usuário não encontrado.", "danger")
                return redirect(url_for("management_panel"))
        token = flask_app.serializer.dumps(user.email, salt="password-reset-salt")
        reset_url = url_for("reset_password", token=token, _external=True)
        html = render_template("emails/reset_password.html", reset_url=reset_url)
        if flask_app.send_email(user.email, "Redefinição de Senha Solicitada", html):
                flash("Link de redefinição enviado para o e-mail do usuário.", "success")
        else:
                flash(f"Não foi possível enviar o e-mail. Link de redefinição: {reset_url}", "warning")
        return redirect(url_for("view_employee_logs", employee_id=user_id))


def _load_journey_choices(uow, form):
        with uow:
                journeys = services.list_journey_types(uow)
                choices = [(journey.journey_id, journey.name) for journey in journeys]
        form.journey_type.choices = [(0, "Selecione um template...")] + choices


def _apply_schedule_form(uow, employee_id, form):
        try:
                journey_id = int(request.form.get("journey_type", 0))
                rotation_start = _parse_rotation_start(form.rotation_start_date.data)
                values = _resolve_schedule(uow, form, journey_id)
                services.set_work_schedule(
                        uow, current_user.id, employee_id,
                        values.arrival, values.lunch_start, values.lunch_end, values.departure,
                        values.tolerance,
                        has_lunch_break=values.has_lunch_break,
                        schedule_type=values.schedule_type,
                        rotation_start_date=rotation_start,
                )
                if journey_id == 0 and form.save_as_new.data:
                        _save_journey_template(uow, form, values)
                flash("Horário de trabalho configurado.", "success")
                return redirect(url_for("view_employee_logs", employee_id=employee_id))
        except Exception as error:
                flash(f"Erro: {str(error)}", "danger")
                return None


def _save_journey_template(uow, form, values):
        services.create_journey_type(
                uow, current_user.id, form.save_as_new.data,
                values.arrival, values.lunch_start, values.lunch_end, values.departure,
                values.tolerance,
                has_lunch_break=values.has_lunch_break,
                schedule_type=values.schedule_type,
        )
        flash(f"Template '{form.save_as_new.data}' salvo!", "info")


def _resolve_schedule(uow, form, journey_id):
        if journey_id > 0:
                journey = services.get_journey_type(uow, journey_id)
                if not journey:
                        raise ValueError("Modelo de jornada não encontrado.")
                return _ScheduleValues(
                        journey.expected_arrival,
                        journey.expected_lunch_start,
                        journey.expected_lunch_end,
                        journey.expected_departure,
                        journey.tolerance_minutes,
                        journey.has_lunch_break,
                        journey.schedule_type.value,
                )
        return _ScheduleValues(
                parse_time(form.arrival.data),
                parse_time(form.lunch_start.data),
                parse_time(form.lunch_end.data),
                parse_time(form.departure.data),
                int(form.tolerance.data),
                form.has_lunch_break.data,
                form.schedule_type.data,
        )


def _parse_rotation_start(value):
        if not value:
                return None
        try:
                return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
                return None


def _prefill_schedule_form(form, employee):
        if request.method == "POST" or not employee.work_schedule:
                return
        schedule = employee.work_schedule
        form.arrival.data = schedule.expected_arrival.strftime("%H:%M")
        form.has_lunch_break.data = schedule.has_lunch_break
        form.lunch_start.data = schedule.expected_lunch_start.strftime("%H:%M") if schedule.expected_lunch_start else ""
        form.lunch_end.data = schedule.expected_lunch_end.strftime("%H:%M") if schedule.expected_lunch_end else ""
        form.departure.data = schedule.expected_departure.strftime("%H:%M")
        form.tolerance.data = str(schedule.tolerance_minutes)


def _create_journey_from_form(uow, form):
        services.create_journey_type(
                uow, current_user.id, form.name.data,
                parse_time(form.arrival.data),
                parse_time(form.lunch_start.data),
                parse_time(form.lunch_end.data),
                parse_time(form.departure.data),
                int(form.tolerance.data),
                has_lunch_break=form.has_lunch_break.data,
                schedule_type=form.schedule_type.data,
        )


def _journey_payload(journey):
        return {
                "arrival": journey.expected_arrival.strftime("%H:%M"),
                "has_lunch_break": journey.has_lunch_break,
                "lunch_start": journey.expected_lunch_start.strftime("%H:%M") if journey.expected_lunch_start else "",
                "lunch_end": journey.expected_lunch_end.strftime("%H:%M") if journey.expected_lunch_end else "",
                "departure": journey.expected_departure.strftime("%H:%M"),
                "tolerance": journey.tolerance_minutes,
                "schedule_type": journey.schedule_type.value,
        }


def _update_journey_from_form(uow, journey_id, form):
        try:
                services.update_journey_type(
                        uow, current_user.id, journey_id, form.name.data,
                        parse_time(form.arrival.data),
                        parse_time(form.lunch_start.data),
                        parse_time(form.lunch_end.data),
                        parse_time(form.departure.data),
                        int(form.tolerance.data),
                        has_lunch_break=form.has_lunch_break.data,
                        schedule_type=form.schedule_type.data,
                )
                flash("Tipo de Jornada atualizado.", "success")
                return redirect(url_for("manage_journeys"))
        except Exception as error:
                flash(f"Erro: {str(error)}", "danger")
                return None


def _prefill_journey_form(form, journey):
        form.name.data = journey.name
        form.has_lunch_break.data = journey.has_lunch_break
        form.arrival.data = journey.expected_arrival.strftime("%H:%M")
        form.lunch_start.data = journey.expected_lunch_start.strftime("%H:%M") if journey.expected_lunch_start else ""
        form.lunch_end.data = journey.expected_lunch_end.strftime("%H:%M") if journey.expected_lunch_end else ""
        form.departure.data = journey.expected_departure.strftime("%H:%M")
        form.tolerance.data = str(journey.tolerance_minutes)
        form.schedule_type.data = journey.schedule_type.value
