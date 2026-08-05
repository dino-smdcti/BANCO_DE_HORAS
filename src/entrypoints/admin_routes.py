from datetime import datetime, timedelta

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from src.domain.model import AuditLog, CompanySettings, User
from src.entrypoints.web_helpers import new_uow


def register_routes(app):
        app.add_url_rule("/admin/audit-logs", "audit_logs", audit_logs)
        app.add_url_rule("/admin/settings", "admin_settings", admin_settings, methods=["GET", "POST"])


@login_required
def audit_logs():
        if current_user.role not in ["admin", "gestor"]:
                flash("Acesso restrito ao Administrador.", "danger")
                return redirect(url_for("dashboard"))
        uow = new_uow()
        with uow:
                return _render_audit_logs(uow)


@login_required
def admin_settings():
        if current_user.role not in ["admin", "gestor"]:
                flash("Acesso restrito ao Administrador.", "danger")
                return redirect(url_for("dashboard"))
        uow = new_uow()
        if request.method == "POST":
                _update_settings(uow)
                return redirect(url_for("admin_settings"))
        with uow:
                settings = uow.session.execute(select(CompanySettings)).scalar_one_or_none()
                return render_template("admin_settings.html", settings=settings)


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
                query = query.where(AuditLog.timestamp >= datetime.strptime(start_date, "%Y-%m-%d"))
        end_date = request.args.get("end_date")
        if end_date:
                query = query.where(AuditLog.timestamp <= datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))
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
        start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d").date()
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
