from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from src.entrypoints.decorators import handle_errors, manager_required
from src.entrypoints.web_helpers import INVALID_DATE, is_management_role, new_uow, parse_date
from src.service_layer import services


def register_routes(app):
        app.add_url_rule("/work/tasks", "work_tasks", work_tasks)
        app.add_url_rule("/work/tasks/create", "work_tasks_create", work_tasks_create, methods=["POST"])
        app.add_url_rule("/work/tasks/<int:task_id>/status", "work_tasks_status", work_tasks_status, methods=["POST"])
        app.add_url_rule("/work/tasks/<int:task_id>/edit", "work_tasks_edit", work_tasks_edit, methods=["POST"])
        app.add_url_rule("/work/tasks/<int:task_id>/delete", "work_tasks_delete", work_tasks_delete, methods=["POST"])
        app.add_url_rule("/work/tasks/<int:task_id>/items/add", "work_tasks_items_add", work_tasks_items_add, methods=["POST"])
        app.add_url_rule("/work/tasks/<int:task_id>/items/<int:item_id>/toggle", "work_tasks_items_toggle", work_tasks_items_toggle, methods=["POST"])
        app.add_url_rule("/work/tasks/<int:task_id>/items/<int:item_id>/remove", "work_tasks_items_remove", work_tasks_items_remove, methods=["POST"])


def _optional_date(value):
        """Parse an optional date; None when empty/invalid, else the date object."""
        parsed = parse_date(value)
        if parsed is INVALID_DATE or parsed is None:
                return None
        return parsed


@login_required
@handle_errors
def work_tasks():
        uow = new_uow()
        with uow:
                tasks = services.list_tasks(uow, current_user.id)
                all_teams = services.list_teams(uow)
                all_users = uow.users.list_all()
                managed = all_teams if is_management_role(current_user.role) else []
                team_labels = {team.team_id: team.name for team in all_teams}
                user_labels = {u.user_id: (u.profile.full_name or u.email) for u in all_users}
                users = sorted(all_users, key=lambda u: (u.profile.full_name or u.email).lower())
                return render_template(
                        "work_tasks.html",
                        tasks=tasks,
                        teams=managed,
                        users=users,
                        team_labels=team_labels,
                        user_labels=user_labels,
                        user_role=current_user.role,
                )


@login_required
@manager_required
@handle_errors
def work_tasks_create():
        uow = new_uow()
        team_id = request.form.get("team_id")
        try:
                services.create_task(
                        uow,
                        current_user.id,
                        team_id=team_id,
                        title=request.form.get("title"),
                        description=request.form.get("description"),
                        assignee_id=request.form.get("assignee_id") or None,
                        due_date=_optional_date(request.form.get("due_date")),
                )
                flash("Tarefa criada.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_tasks"))


@login_required
@handle_errors
def work_tasks_status(task_id):
        uow = new_uow()
        try:
                services.update_task_status(uow, current_user.id, task_id, request.form.get("status"))
                flash("Status atualizado.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_tasks"))


@login_required
@manager_required
@handle_errors
def work_tasks_edit(task_id):
        uow = new_uow()
        try:
                services.edit_task(
                        uow,
                        current_user.id,
                        task_id,
                        title=request.form.get("title"),
                        description=request.form.get("description"),
                        assignee_id=request.form.get("assignee_id") or None,
                        due_date=_optional_date(request.form.get("due_date") or None),
                )
                flash("Tarefa atualizada.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_tasks"))


@login_required
@manager_required
@handle_errors
def work_tasks_delete(task_id):
        uow = new_uow()
        try:
                services.delete_task(uow, current_user.id, task_id)
                flash("Tarefa excluída.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_tasks"))


@login_required
@handle_errors
def work_tasks_items_add(task_id):
        uow = new_uow()
        try:
                services.add_checklist_item(uow, current_user.id, task_id, request.form.get("label"))
                flash("Item adicionado.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_tasks"))


@login_required
@handle_errors
def work_tasks_items_toggle(task_id, item_id):
        uow = new_uow()
        done = request.form.get("done") in ("1", "true", "on")
        try:
                services.toggle_checklist_item(uow, current_user.id, task_id, item_id, done)
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_tasks"))


@login_required
@handle_errors
def work_tasks_items_remove(task_id, item_id):
        uow = new_uow()
        try:
                services.remove_checklist_item(uow, current_user.id, task_id, item_id)
                flash("Item removido.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_tasks"))