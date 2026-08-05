from datetime import date, datetime

from flask import flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from src.entrypoints.forms import ProfileForm
from src.entrypoints.web_helpers import INVALID_DATE, get_maps_url, is_management_role, new_uow, parse_date
from src.service_layer import services


def register_routes(app):
        app.add_url_rule("/dashboard", "dashboard", dashboard)
        app.add_url_rule("/choose-journey", "choose_journey", choose_journey, methods=["GET", "POST"])
        app.add_url_rule("/complete-profile", "complete_profile", complete_profile, methods=["GET", "POST"])
        app.add_url_rule("/profile", "profile", profile, methods=["GET", "POST"])
        app.add_url_rule("/submit-correction", "submit_correction", submit_correction, methods=["POST"])
        app.add_url_rule("/notifications/read", "mark_notifications_read", mark_notifications_read, methods=["POST"])
        app.add_url_rule("/clock", "clock", clock, methods=["POST"])
        app.add_url_rule("/update-note", "update_note", update_note, methods=["POST"])
        app.add_url_rule("/download-report/<int:user_id>", "download_report", download_report)


@login_required
def dashboard():
        if not current_user.is_profile_complete:
                return redirect(url_for("complete_profile"))
        if current_user.role == "employee" and not current_user.has_schedule:
                return redirect(url_for("choose_journey"))
        filter_date_str = request.args.get("date")
        uow = new_uow()
        with uow:
                user = uow.users.get_user_by_id(current_user.id)
                if not user:
                        flash("Usuário não encontrado", "danger")
                        return redirect(url_for("logout"))
                uow.session.refresh(user)
                return _render_dashboard(user, filter_date_str)


@login_required
def choose_journey():
        if current_user.role != "employee":
                return redirect(url_for("dashboard"))
        uow = new_uow()
        with uow:
                return _choose_journey(uow)


@login_required
def complete_profile():
        if current_user.is_profile_complete:
                return redirect(url_for("dashboard"))
        form = ProfileForm()
        if form.validate_on_submit():
                _save_profile(current_user.id, form)
                flash("Perfil preenchido com sucesso!", "success")
                return redirect(url_for("dashboard"))
        return render_template("complete_profile.html", form=form)


@login_required
def profile():
        uow = new_uow()
        with uow:
                return _render_profile(uow)


@login_required
def submit_correction():
        try:
                ponto_date = datetime.strptime(request.form.get("ponto_date"), "%Y-%m-%d").date()
                proposed_time = datetime.strptime(request.form.get("proposed_time"), "%H:%M").time()
                uow = new_uow()
                services.submit_correction_request(uow, current_user.id, ponto_date, request.form.get("stage"), proposed_time)
                flash("Pedido de correção enviado para análise.", "success")
        except Exception as error:
                flash(f"Erro ao enviar correção: {str(error)}", "danger")
        return redirect(url_for("dashboard"))


@login_required
def mark_notifications_read():
        uow = new_uow()
        services.mark_notifications_as_read(uow, current_user.id)
        return {"status": "ok"}


@login_required
def clock():
        uow = new_uow()
        try:
                message = services.clock_in_out(uow, current_user.id, request.form.get("location"), stage=request.form.get("stage"), notes=request.form.get("notes"))
                flash(message, "info")
        except ValueError as error:
                flash(str(error), "warning")
        return redirect(url_for("dashboard"))


@login_required
def update_note():
        try:
                entry_date = datetime.strptime(request.form.get("entry_date"), "%Y-%m-%d").date()
                _save_note(current_user.id, entry_date, request.form.get("notes"))
        except Exception as error:
                flash(f"Erro ao salvar nota: {str(error)}", "danger")
        return redirect(url_for("dashboard"))


@login_required
def download_report(user_id):
        if current_user.id != user_id and not is_management_role(current_user.role):
                flash("Acesso não autorizado.", "danger")
                return redirect(url_for("dashboard"))
        start_date = _report_date("start_date")
        if start_date is INVALID_DATE:
                flash("Formato de data inválido.", "danger")
                return redirect(url_for("dashboard"))
        end_date = _report_date("end_date")
        if end_date is INVALID_DATE:
                flash("Formato de data inválido.", "danger")
                return redirect(url_for("dashboard"))
        return _send_report(user_id, start_date, end_date)


def _render_dashboard(user, filter_date_str):
        filter_date = parse_date(filter_date_str)
        today_date = date.today()
        ponto_hoje = _entry_for(user, today_date)
        expected_daily = _expected_daily(user.work_schedule)
        return render_template(
                "employee_dashboard.html",
                recent_entries=_recent_entries(user, filter_date),
                current_stage=ponto_hoje.current_stage if ponto_hoje else "Chegada",
                sched_data=_sched_data(user.work_schedule),
                maps_url=_maps_url(ponto_hoje),
                filter_date=filter_date_str,
                saldo_dia=_saldo_dia(ponto_hoje, expected_daily),
                expected_daily=expected_daily,
                saldo_total=user.total_balance if user.work_schedule else 0,
                worked_hoje=ponto_hoje.worked_minutes if ponto_hoje else 0,
                ponto_hoje=ponto_hoje,
                last_clock_time=_last_clock_time(ponto_hoje),
        )


def _choose_journey(uow):
        user = uow.users.get_user_by_id(current_user.id)
        if user.work_schedule:
                return redirect(url_for("dashboard"))
        journeys = services.list_journey_types(uow)
        if not journeys:
                flash("Nenhuma jornada disponível. Por favor, crie uma jornada primeiro.", "warning")
                return redirect(url_for("manage_journeys"))
        if request.method == "POST":
                _apply_journey_selection(uow, user)
        return render_template("set_schedule.html", employee=user, journeys=journeys, self_select=True)


def _apply_journey_selection(uow, user):
        journey_id = request.form.get("journey_id")
        if not journey_id:
                flash("Por favor, selecione uma jornada.", "warning")
                return
        journey = services.get_journey_type(uow, int(journey_id))
        if journey:
                services.set_work_schedule(
                        uow, current_user.id, current_user.id,
                        journey.expected_arrival,
                        journey.expected_lunch_start,
                        journey.expected_lunch_end,
                        journey.expected_departure,
                        journey.tolerance_minutes,
                )
                flash("Jornada de trabalho selecionada com sucesso!", "success")


def _save_profile(user_id, form):
        uow = new_uow()
        services.update_user_profile(
                uow,
                user_id,
                form.registration_number.data,
                form.cpf.data,
                form.department.data,
                form.position.data,
                form.secretariat.data,
                form.full_name.data,
                birth_date=form.birth_date.data,
        )


def _render_profile(uow):
        user = uow.users.get_user_by_id(current_user.id)
        if request.method == "POST":
                return _apply_profile_post(uow, user)
        return render_template("profile.html", user=user)


def _apply_profile_post(uow, user):
        try:
                _update_own_profile(uow, user)
                flash("Perfil atualizado!", "success")
                return redirect(url_for("dashboard"))
        except ValueError as error:
                message = str(error)
                if "already exists" in message:
                        message = "Este e-mail já está em uso por outro usuário."
                flash(message, "danger")
                return render_template("profile.html", user=user)


def _update_own_profile(uow, user):
        email = request.form.get("email")
        password = request.form.get("password") or None
        email_notifications = bool(request.form.get("email_notifications"))
        services.update_credentials(uow, current_user.id, email, password, email_notifications)
        if current_user.role in ["admin", "gestor"]:
                _update_professional_profile(uow, user)


def _update_professional_profile(uow, user):
        services.update_user_profile(
                uow,
                current_user.id,
                request.form.get("registration_number"),
                request.form.get("cpf"),
                request.form.get("department"),
                request.form.get("position"),
                request.form.get("secretariat"),
                request.form.get("full_name"),
                start_analysis_date=_analysis_date(),
                birth_date=_birth_date(),
        )


def _analysis_date():
        raw = request.form.get("start_analysis_date")
        return datetime.strptime(raw, "%Y-%m-%d").date() if raw else None


def _birth_date():
        raw = request.form.get("birth_date")
        return datetime.strptime(raw, "%Y-%m-%d").date() if raw else None


def _entry_for(user, target_date):
        return next((entry for entry in user.time_entries if entry.entry_date == target_date), None)


def _recent_entries(user, filter_date):
        if filter_date:
                return [entry for entry in user.time_entries if entry.entry_date == filter_date]
        return sorted(user.time_entries, key=lambda entry: entry.entry_date, reverse=True)[:10]


def _minutes_between(t1, t2):
        if not t1 or not t2:
                return 0
        return int((datetime.combine(date.min, t2) - datetime.combine(date.min, t1)).total_seconds() / 60)


def _expected_daily(schedule):
        if not schedule:
                return 0
        return _minutes_between(schedule.expected_arrival, schedule.expected_lunch_start) + _minutes_between(schedule.expected_lunch_end, schedule.expected_departure)


def _saldo_dia(ponto_hoje, expected_daily):
        if not ponto_hoje:
                return 0
        return ponto_hoje.worked_minutes - expected_daily


def _sched_data(schedule):
        if not schedule:
                return None
        return {
                "expected_arrival": schedule.expected_arrival.strftime("%H:%M"),
                "expected_lunch_start": schedule.expected_lunch_start.strftime("%H:%M") if schedule.expected_lunch_start else None,
                "expected_lunch_end": schedule.expected_lunch_end.strftime("%H:%M") if schedule.expected_lunch_end else None,
                "expected_departure": schedule.expected_departure.strftime("%H:%M"),
                "has_lunch_break": schedule.has_lunch_break,
        }


def _last_clock_time(ponto_hoje):
        if not ponto_hoje:
                return None
        times = [ponto_hoje.departure, ponto_hoje.lunch_end, ponto_hoje.lunch_start, ponto_hoje.arrival]
        return next((value.strftime("%H:%M:%S") for value in times if value is not None), None)


def _maps_url(ponto_hoje):
        if not ponto_hoje or not ponto_hoje.location_data:
                return None
        locations = ponto_hoje.location_data.split("|")
        last_loc = locations[-1].split(":")[-1].strip()
        return get_maps_url(last_loc)


def _save_note(user_id, entry_date, notes):
        uow = new_uow()
        with uow:
                user = uow.users.get_user_by_id(user_id)
                entry = _entry_for(user, entry_date)
                if entry:
                        entry.notes = notes
                        uow.commit()
                        flash("Nota atualizada com sucesso.", "success")
                else:
                        flash("Registro não encontrado.", "warning")


def _report_date(name):
        value = request.args.get(name)
        return parse_date(value)


def _send_report(user_id, start_date, end_date):
        uow = new_uow()
        excel_file = services.generate_excel_report(uow, user_id, start_date, end_date)
        emp_name = _employee_slug(uow, user_id)
        filename = f"relatorio_{emp_name}_{_date_slug(start_date, 'inicio')}_{_date_slug(end_date, 'fim')}.xlsx"
        return send_file(
                excel_file,
                as_attachment=True,
                download_name=filename,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def _employee_slug(uow, user_id):
        with uow:
                user = uow.users.get_user_by_id(user_id)
                if user and user.profile:
                        return (user.profile.full_name or "funcionario").replace(" ", "_").lower()
        return "funcionario"


def _date_slug(value, fallback):
        return value.strftime("%Y%m%d") if value else fallback
