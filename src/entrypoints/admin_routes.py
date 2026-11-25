from datetime import datetime, timedelta, date

from flask import flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from src.domain.model import AuditLog, CompanySettings, User
from src.entrypoints.decorators import admin_required, handle_errors
from src.entrypoints.web_helpers import new_uow, parse_date_arg
from src.service_layer import services
from src.config import DATE_FORMAT


def register_routes(app):
        app.add_url_rule("/admin/audit-logs", "audit_logs", audit_logs)
        app.add_url_rule("/admin/settings", "admin_settings", admin_settings, methods=["GET", "POST"])
        app.add_url_rule("/admin/teams", "teams_page", teams_page)
        app.add_url_rule("/admin/teams/create", "create_team", create_team_route, methods=["POST"])
        app.add_url_rule("/admin/teams/assign", "assign_user_team", assign_team_route, methods=["POST"])
        app.add_url_rule("/metrics", "metrics_panel", metrics_panel)
        app.add_url_rule("/report/bulk", "bulk_report", bulk_report)


@login_required
@admin_required
@handle_errors
def audit_logs():
        uow = new_uow()
        with uow:
                return _render_audit_logs(uow)


@login_required
@admin_required
@handle_errors
def admin_settings():
        uow = new_uow()
        if request.method == "POST":
                _update_settings(uow)
                return redirect(url_for("admin_settings"))
        with uow:
                settings = uow.session.execute(select(CompanySettings)).scalar_one_or_none()
                return render_template("admin_settings.html", settings=settings)


@login_required
@admin_required
@handle_errors
def teams_page():
        uow = new_uow()
        with uow:
                teams = services.list_teams(uow)
                users = sorted(uow.users.list_all(), key=lambda u: (u.profile.full_name or u.email).lower())
                return render_template("teams.html", teams=teams, users=users)


@login_required
@admin_required
@handle_errors
def create_team_route():
        uow = new_uow()
        try:
                services.create_team(uow, current_user.id, request.form.get("name"), request.form.get("secretariat"))
                flash("Time criado.", "success")
        except ValueError as error:
                flash(str(error), "danger")
        return redirect(url_for("teams_page"))


@login_required
@admin_required
@handle_errors
def assign_team_route():
        uow = new_uow()
        try:
                services.assign_user_team(uow, current_user.id, int(request.form.get("user_id")), request.form.get("team_id") or None)
                flash("Time do usuário atualizado.", "success")
        except ValueError as error:
                flash(str(error), "danger")
        return redirect(url_for("teams_page"))


@login_required
@admin_required
@handle_errors
def metrics_panel():
        uow = new_uow()
        with uow:
                start_date, end_date = _metrics_period(uow)
                team_id = _int_or_none(request.args.get("team_id"))
                emp_id = _int_or_none(request.args.get("employee_id"))
                users = services.list_clocking_users(uow, team_id)
                if emp_id:
                        users = [user for user in users if user.user_id == emp_id]
                rows = [_metrics_row(uow, user, start_date, end_date) for user in users]
                return render_template(
                        "metrics.html",
                        rows=rows,
                        teams=services.list_teams(uow),
                        all_users=services.list_clocking_users(uow),
                        start_date=start_date,
                        end_date=end_date,
                        team_id=team_id,
                        emp_id=emp_id,
                )


@login_required
@admin_required
@handle_errors
def bulk_report():
        uow = new_uow()
        try:
                with uow:
                        start_date, end_date = _metrics_period(uow)
                        team_id = _int_or_none(request.args.get("team_id"))
                        buffer = services.generate_bulk_report_excel(uow, start_date, end_date, team_id)
                filename = f"relatorio_banco_horas_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"
                return send_file(
                        buffer,
                        as_attachment=True,
                        download_name=filename,
                        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        except Exception as error:
                flash(f"Erro ao gerar relatório: {str(error)}", "danger")
                return redirect(url_for("metrics_panel"))


def _metrics_period(uow):
        start_str = request.args.get("start_date")
        end_str = request.args.get("end_date")
        start_date = parse_date_arg(start_str) if start_str else services.get_start_analysis_date(uow)
        end_date = parse_date_arg(end_str) if end_str else date.today()
        return start_date, end_date


def _metrics_row(uow, user, start_date, end_date):
        metrics = services.compute_period_metrics(user, start_date, end_date)
        return {
                "user": user,
                "name": user.profile.full_name or user.email,
                "registration": user.profile.registration_number or "-",
                "team_name": services.team_name_for(uow, user),
                "worked": services.format_minutes(metrics["worked_minutes"]),
                "expected": services.format_minutes(metrics["expected_minutes"]),
                "missed": services.format_minutes(metrics["missed_minutes"]),
                "conceded": services.format_minutes(metrics["conceded_minutes"]),
                "balance": services.format_minutes(metrics["balance_minutes"]),
                "balance_negative": metrics["balance_minutes"] < 0,
        }


def _int_or_none(value):
        if not value:
                return None
        try:
                return int(value)
        except (ValueError, TypeError):
                return None


def _render_audit_logs(uow):
        logs = uow.session.execute(_audit_query().order_by(AuditLog.timestamp.desc()).limit(200)).scalars().all()
        return render_template(
                "audit_logs.html",
                audit_logs=logs,
                logs_display=[_log_row(uow, log) for log in logs],
                unique_users=_unique_actors(uow),
        )


def _unique_actors(uow):
        actor_ids = uow.session.execute(select(AuditLog.user_id).where(AuditLog.user_id.isnot(None)).distinct()).scalars().all()
        actors = [uow.users.get_user_by_id(actor_id) for actor_id in actor_ids]
        return sorted((actor for actor in actors if actor), key=lambda actor: (actor.profile.full_name or actor.email).lower())


def _audit_query():
        query = select(AuditLog).join(User, AuditLog.user_id == User.user_id)
        query = query.where(AuditLog.action.notin_(["CLOCK_EVENT", "SUBMIT_CORRECTION_REQUEST"]))
        query = _apply_actor_filter(query, request.args.get("actor_search"))
        query = _apply_action_filter(query, request.args.get("action_type"))
        query = _apply_date_filters(query)
        return query


def _apply_actor_filter(query, actor_search):
        if not actor_search:
                return query
        if actor_search.isdigit():
                return query.where(AuditLog.user_id == int(actor_search))
        return query.where(
                (User.email.contains(actor_search)) |
                (User.full_name == actor_search) |
                (User.full_name.contains(actor_search))
        )


def _apply_action_filter(query, action_type):
        if action_type:
                query = query.where(AuditLog.action == action_type)
        return query


def _apply_date_filters(query):
        start_date = request.args.get("start_date")
        if start_date:
                query = query.where(AuditLog.timestamp >= datetime.strptime(start_date, DATE_FORMAT))
        end_date = request.args.get("end_date")
        if end_date:
                query = query.where(AuditLog.timestamp <= datetime.strptime(end_date, DATE_FORMAT) + timedelta(days=1))
        return query


def _log_row(uow, log):
        actor = uow.users.get_user_by_id(log.user_id) if log.user_id else None
        target = uow.users.get_user_by_id(log.target_id) if log.target_id else None
        return {
                "timestamp": log.timestamp,
                "action": log.action,
                "details": log.details,
                "actor_name": _person_label(actor),
                "actor_email": actor.email if actor else "",
                "target_name": _person_label(target, missing=""),
                "target_email": target.email if target else "",
        }


def _person_label(person, missing="Sistema"):
        if not person:
                return missing
        if person.profile:
                return person.profile.full_name
        return person.email


def _update_settings(uow):
        lat = float(request.form.get("lat"))
        lon = float(request.form.get("lon"))
        start_date = parse_date_arg(request.form.get("start_date"))
        with uow:
                settings = uow.session.execute(select(CompanySettings)).scalar_one_or_none()
                if settings:
                        settings.lat = lat
                        settings.lon = lon
                        settings.start_analysis_date = start_date
                else:
                        uow.session.add(CompanySettings(lat=lat, lon=lon, start_analysis_date=start_date))
                uow.commit()
                flash("Configurações atualizadas.", "success")
