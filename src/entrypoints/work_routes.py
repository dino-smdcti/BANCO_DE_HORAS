from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from src.config import BOARD_STAGES, TASK_STATUS_LABELS, TASK_STATUSES, WORKFORCE_ENABLED
from src.entrypoints.decorators import handle_errors, manager_required
from src.entrypoints.web_helpers import INVALID_DATE, is_management_role, new_uow, parse_date
from src.service_layer import services


def register_routes(app):
        if not WORKFORCE_ENABLED:
                # Workforce expansion is behind a soft-launch gate; when disabled
                # no /work/* routes are exposed and the module stays dormant.
                return
        app.add_url_rule("/work", "work_dashboard", work_dashboard)
        app.add_url_rule("/work/tasks", "work_tasks", work_tasks)
        app.add_url_rule("/work/tasks/create", "work_tasks_create", work_tasks_create, methods=["POST"])
        app.add_url_rule("/work/tasks/<int:task_id>/status", "work_tasks_status", work_tasks_status, methods=["POST"])
        app.add_url_rule("/work/tasks/<int:task_id>/edit", "work_tasks_edit", work_tasks_edit, methods=["POST"])
        app.add_url_rule("/work/tasks/<int:task_id>/delete", "work_tasks_delete", work_tasks_delete, methods=["POST"])
        app.add_url_rule("/work/tasks/<int:task_id>/items/add", "work_tasks_items_add", work_tasks_items_add, methods=["POST"])
        app.add_url_rule("/work/tasks/<int:task_id>/items/<int:item_id>/toggle", "work_tasks_items_toggle", work_tasks_items_toggle, methods=["POST"])
        app.add_url_rule("/work/tasks/<int:task_id>/items/<int:item_id>/remove", "work_tasks_items_remove", work_tasks_items_remove, methods=["POST"])
        app.add_url_rule("/work/accomplishments", "work_accomplishments", work_accomplishments)
        app.add_url_rule("/work/accomplishments/create", "work_accomplishments_create", work_accomplishments_create, methods=["POST"])
        app.add_url_rule("/work/accomplishments/<int:accomplishment_id>/edit", "work_accomplishments_edit", work_accomplishments_edit, methods=["POST"])
        app.add_url_rule("/work/accomplishments/<int:accomplishment_id>/delete", "work_accomplishments_delete", work_accomplishments_delete, methods=["POST"])
        app.add_url_rule("/work/ideas", "work_ideas", work_ideas)
        app.add_url_rule("/work/ideas/create", "work_ideas_create", work_ideas_create, methods=["POST"])
        app.add_url_rule("/work/ideas/<int:idea_id>/vote", "work_ideas_vote", work_ideas_vote, methods=["POST"])
        app.add_url_rule("/work/ideas/<int:idea_id>/status", "work_ideas_status", work_ideas_status, methods=["POST"])
        app.add_url_rule("/work/ideas/<int:idea_id>/delete", "work_ideas_delete", work_ideas_delete, methods=["POST"])
        app.add_url_rule("/work/teams", "work_teams", work_teams)
        app.add_url_rule("/work/teams/<int:team_id>/update", "work_teams_update", work_teams_update, methods=["POST"])
        app.add_url_rule("/work/5s", "work_5s", work_5s)
        app.add_url_rule("/work/5s/create", "work_5s_create", work_5s_create, methods=["POST"])
        app.add_url_rule("/work/5s/<int:s5_audit_id>/delete", "work_5s_delete", work_5s_delete, methods=["POST"])
        app.add_url_rule("/work/culture/wiki", "work_culture_wiki", work_culture_wiki)
        app.add_url_rule("/work/culture/wiki/create", "work_culture_wiki_create", work_culture_wiki_create, methods=["POST"])
        app.add_url_rule("/work/culture/wiki/<int:wiki_article_id>/update", "work_culture_wiki_update", work_culture_wiki_update, methods=["POST"])
        app.add_url_rule("/work/culture/wiki/<int:wiki_article_id>/delete", "work_culture_wiki_delete", work_culture_wiki_delete, methods=["POST"])
        app.add_url_rule("/work/culture/likes", "work_culture_likes", work_culture_likes)
        app.add_url_rule("/work/culture/likes/create", "work_culture_likes_create", work_culture_likes_create, methods=["POST"])
        app.add_url_rule("/work/culture/likes/<int:kudo_id>/delete", "work_culture_likes_delete", work_culture_likes_delete, methods=["POST"])
        app.add_url_rule("/work/culture/events", "work_culture_events", work_culture_events)
        app.add_url_rule("/work/culture/events/create", "work_culture_events_create", work_culture_events_create, methods=["POST"])
        app.add_url_rule("/work/culture/events/<int:event_id>/delete", "work_culture_events_delete", work_culture_events_delete, methods=["POST"])
        app.add_url_rule("/work/reports", "work_reports", work_reports)
        app.add_url_rule("/work/exec", "work_exec", work_exec)
        app.add_url_rule("/work/exec/<int:team_id>", "work_exec_team", work_exec_team)


def _optional_date(value):
        """Parse an optional date; None when empty/invalid, else the date object."""
        parsed = parse_date(value)
        if parsed is INVALID_DATE or parsed is None:
                return None
        return parsed


@login_required
@handle_errors
def work_dashboard():
        uow = new_uow()
        with uow:
                kpis = services.list_exec_kpis(uow, current_user.id)
                all_teams, team_labels, user_labels, users = _culture_context(uow)
                scoped = _scoped_team_list(uow, all_teams)
                scoped_ids = {team.team_id for team in scoped}
                in_scope = [k for k in kpis if k["team_id"] in scoped_ids]
                summary = _dashboard_summary(in_scope)
                recent = _recent_activity(uow, scoped_ids)
                tasks = services.list_tasks(uow, current_user.id)
                tasks_by_stage = _group_tasks_by_stage(tasks)
                stage_counts = {stage: len(tasks_by_stage.get(stage, [])) for stage in BOARD_STAGES}
                task_stage_map = {task.task_id: _normalise_stage(task.status) for task in tasks}
                metrics = services.dashboard_metrics(uow, current_user.id)
                return render_template(
                        "work_dashboard.html",
                        kpis=in_scope,
                        summary=summary,
                        recent=recent,
                        team_labels=team_labels,
                        user_labels=user_labels,
                        user_role=current_user.role,
                        board_stages=BOARD_STAGES,
                        stage_labels=TASK_STATUS_LABELS,
                        tasks_by_stage=tasks_by_stage,
                        stage_counts=stage_counts,
                        task_stage_map=task_stage_map,
                        metrics=metrics,
                )


def _normalise_stage(status):
        """Map legacy task statuses to the current board stages."""
        legacy = {"todo": "backlog", "in_progress": "in_execution"}
        return legacy.get(status, status)


def _group_tasks_by_stage(tasks):
        """Bucket tasks into board columns, newest first within each column."""
        grouped = {stage: [] for stage in BOARD_STAGES}
        for task in tasks:
                stage = _normalise_stage(task.status)
                if stage in grouped:
                        grouped[stage].append(task)
        for stage in grouped:
                grouped[stage].sort(
                        key=lambda t: (t.created_at is None, t.created_at),
                        reverse=True,
                )
        return grouped


def _dashboard_summary(kpis):
        return {
                "teams": len(kpis),
                "members": sum(k["members"] for k in kpis),
                "open_tasks": sum(k["open_tasks"] for k in kpis),
                "open_ideas": sum(k["open_ideas"] for k in kpis),
                "implemented_ideas": sum(k["implemented_ideas"] for k in kpis),
                "accomplishments": sum(k["accomplishments"] for k in kpis),
                "kudos": sum(k["kudos"] for k in kpis),
                "avg_5s": round((sum(k["avg_5s"] for k in kpis) / len(kpis)) if kpis else 0.0, 1),
        }


def _recent_activity(uow, scoped_ids):
        recent = []
        for team_id in scoped_ids:
                for task in uow.users.list_tasks_by_team(team_id):
                        recent.append(("task", task))
                for acc in uow.users.list_accomplishments_by_team(team_id):
                        recent.append(("accomplishment", acc))
        recent.sort(key=lambda item: getattr(item[1], "created_at", None) or _default_date(), reverse=True)
        return recent[:8]


def _default_date():
        from datetime import datetime
        return datetime(1970, 1, 1)


def _parse_request_dates():
        """Read ?from= & ?to= query params into date objects (None when blank)."""
        period_start = _optional_date(request.args.get("from")) if "from" in request.args else None
        period_end = _optional_date(request.args.get("to")) if "to" in request.args else None
        if period_start and period_end and period_start > period_end:
                period_start, period_end = period_end, period_start
        return period_start, period_end


@login_required
@handle_errors
def work_reports():
        uow = new_uow()
        with uow:
                try:
                        period_start, period_end = _parse_request_dates()
                        team_id = request.args.get("team_id", type=int)
                        report = services.build_work_report(
                                uow,
                                current_user.id,
                                period_start=period_start,
                                period_end=period_end,
                                team_id=team_id,
                        )
                except PermissionError as error:
                        flash(str(error), "danger")
                        return redirect(url_for("work_reports"))
                all_teams, team_labels, user_labels, users = _culture_context(uow)
                scoped = _scoped_team_list(uow, all_teams)
                return render_template(
                        "work_reports.html",
                        report=report,
                        scoped_teams=scoped,
                        team_labels=team_labels,
                        user_labels=user_labels,
                        user_role=current_user.role,
                        period_start=report["period_start"],
                        period_end=report["period_end"],
                        selected_team=team_id,
                )


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
                events = services.list_team_events(uow, current_user.id)
                event_labels = {e.event_id: e.title for e in events}
                task_progress = {
                        task.task_id: _task_progress(task)
                        for task in tasks
                }
                return render_template(
                        "work_tasks.html",
                        tasks=tasks,
                        teams=managed,
                        users=users,
                        team_labels=team_labels,
                        user_labels=user_labels,
                        events=events,
                        event_labels=event_labels,
                        task_progress=task_progress,
                        user_role=current_user.role,
                        board_stages=BOARD_STAGES,
                        stage_labels=TASK_STATUS_LABELS,
                )


def _task_progress(task):
        """Return (done_count, total_count) for a task's checklist."""
        items = task.checklist_items or []
        total = len(items)
        done = sum(1 for i in items if i.done)
        return done, total


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
                        event_id=request.form.get("event_id") or None,
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
        return redirect(request.referrer or url_for("work_tasks"))


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
                        event_id=request.form.get("event_id") or None,
                        clear_event=not bool(request.form.get("event_id")),
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


@login_required
@handle_errors
def work_accomplishments():
        uow = new_uow()
        with uow:
                accomplishments = services.list_accomplishments(uow, current_user.id)
                all_teams = services.list_teams(uow)
                all_users = uow.users.list_all()
                managed = all_teams if is_management_role(current_user.role) else []
                team_labels = {team.team_id: team.name for team in all_teams}
                user_labels = {u.user_id: (u.profile.full_name or u.email) for u in all_users}
                users = sorted(all_users, key=lambda u: (u.profile.full_name or u.email).lower())
                status_map = {acc.accomplishment_id: services.meta_status(acc) for acc in accomplishments}
                leaderboard = services.meta_leaderboard(uow, current_user.id)
                return render_template(
                        "work_accomplishments.html",
                        accomplishments=accomplishments,
                        teams=managed,
                        users=users,
                        team_labels=team_labels,
                        user_labels=user_labels,
                        user_role=current_user.role,
                        status_map=status_map,
                        status_labels=services.META_STATUS_LABELS,
                        leaderboard=leaderboard,
                )


@login_required
@manager_required
@handle_errors
def work_accomplishments_create():
        uow = new_uow()
        try:
                services.create_accomplishment(
                        uow,
                        current_user.id,
                        team_id=request.form.get("team_id"),
                        title=request.form.get("title"),
                        description=request.form.get("description"),
                        start_date=_optional_date(request.form.get("start_date")),
                        end_date=_optional_date(request.form.get("end_date")),
                        target_date=_optional_date(request.form.get("target_date")),
                        points=request.form.get("points") or 0,
                        achieved_by_user_id=request.form.get("achieved_by_user_id") or None,
                )
                flash("Meta registrada.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_accomplishments"))


@login_required
@manager_required
@handle_errors
def work_accomplishments_edit(accomplishment_id):
        uow = new_uow()
        try:
                services.edit_accomplishment(
                        uow,
                        current_user.id,
                        accomplishment_id,
                        title=request.form.get("title") or None,
                        description=request.form.get("description") or None,
                        start_date=_optional_date(request.form.get("start_date")),
                        end_date=_optional_date(request.form.get("end_date")),
                        target_date=_optional_date(request.form.get("target_date")),
                        points=request.form.get("points") or None,
                        achieved_by_user_id=request.form.get("achieved_by_user_id") or None,
                        clear_end_date=request.form.get("clear_end_date") in ("1", "true", "on"),
                        clear_target_date=request.form.get("clear_target_date") in ("1", "true", "on"),
                )
                flash("Meta atualizada.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_accomplishments"))


@login_required
@manager_required
@handle_errors
def work_accomplishments_delete(accomplishment_id):
        uow = new_uow()
        try:
                services.delete_accomplishment(uow, current_user.id, accomplishment_id)
                flash("Meta excluída.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_accomplishments"))


@login_required
@handle_errors
def work_ideas():
        uow = new_uow()
        with uow:
                category = request.args.get("category")
                ideas = services.list_ideas(uow, current_user.id, category)
                all_teams = services.list_teams(uow)
                all_users = uow.users.list_all()
                scoped = all_teams if is_management_role(current_user.role) else []
                team_labels = {team.team_id: team.name for team in all_teams}
                author_labels = {u.user_id: (u.profile.full_name or u.email) for u in all_users}
                teams = sorted(all_teams, key=lambda t: (t.name or "").lower())
                voted_idea_ids = set()
                for idea in ideas:
                        idea.votes = [] if idea.votes is None else idea.votes
                        if any(v.voter_user_id == current_user.id for v in idea.votes):
                                voted_idea_ids.add(idea.idea_id)
                return render_template(
                        "work_ideas.html",
                        ideas=ideas,
                        teams=teams,
                        team_labels=team_labels,
                        author_labels=author_labels,
                        category=category,
                        user_role=current_user.role,
                        voted_idea_ids=voted_idea_ids,
                )


@login_required
@handle_errors
def work_ideas_create():
        uow = new_uow()
        try:
                team_id = request.form.get("team_id")
                if not team_id:
                        with uow:
                                team_id = uow.users.get_user_by_id(current_user.id).team_id
                services.create_idea(
                        uow,
                        current_user.id,
                        team_id=team_id,
                        title=request.form.get("title"),
                        category=request.form.get("category") or "idea",
                        description=request.form.get("description"),
                )
                flash("Ideia postada.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_ideas"))


@login_required
@handle_errors
def work_ideas_vote(idea_id):
        uow = new_uow()
        try:
                voted = services.vote_idea(uow, current_user.id, idea_id)
                flash("Voto registrado." if voted else "Voto removido.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(request.referrer or url_for("work_ideas"))


@login_required
@manager_required
@handle_errors
def work_ideas_status(idea_id):
        uow = new_uow()
        try:
                services.set_idea_status(
                        uow,
                        current_user.id,
                        idea_id,
                        request.form.get("status"),
                        review_date=_optional_date(request.form.get("review_date")),
                        review_owner=request.form.get("review_owner"),
                )
                flash("Status atualizado.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_ideas"))


@login_required
@handle_errors
def work_ideas_delete(idea_id):
        uow = new_uow()
        try:
                services.delete_idea(uow, current_user.id, idea_id)
                flash("Ideia excluída.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_ideas"))


@login_required
@handle_errors
def work_teams():
        uow = new_uow()
        with uow:
                if is_management_role(current_user.role):
                        from src.service_layer.permissions import scoped_team_ids
                        team_ids = set(scoped_team_ids(uow, current_user.id))
                else:
                        team_ids = {uow.users.get_user_by_id(current_user.id).team_id}
                team_ids = {t for t in team_ids if t}
                rollups = services.team_rollups(uow, team_ids)
                all_teams = services.list_teams(uow)
                team_labels = {team.team_id: team.name for team in all_teams}
                all_users = uow.users.list_all()
                user_labels = {u.user_id: (u.profile.full_name or u.email) for u in all_users}
                users = sorted(all_users, key=lambda u: (u.profile.full_name or u.email).lower())
                can_edit = is_management_role(current_user.role)
                return render_template(
                        "work_teams.html",
                        rollups=rollups,
                        team_labels=team_labels,
                        user_labels=user_labels,
                        users=users,
                        can_edit=can_edit,
                )


@login_required
@manager_required
@handle_errors
def work_teams_update(team_id):
        uow = new_uow()
        try:
                services.scoped_update_team(
                        uow,
                        current_user.id,
                        team_id,
                        name=request.form.get("name"),
                        secretariat=request.form.get("secretariat"),
                        lead_user_id=request.form.get("lead_user_id"),
                )
                flash("Time atualizado.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_teams"))


@login_required
@handle_errors
def work_5s():
        uow = new_uow()
        with uow:
                from src.service_layer.permissions import scoped_team_ids
                from src.service_layer.s5_service import DEFAULT_S5_ITEMS
                audits = services.list_s5_audits(uow, current_user.id)
                all_teams = services.list_teams(uow)
                scoped = set(scoped_team_ids(uow, current_user.id))
                teams = [t for t in all_teams if t.team_id in scoped]
                team_labels = {team.team_id: team.name for team in all_teams}
                auditor_labels = {u.user_id: (u.profile.full_name or u.email) for u in uow.users.list_all()}
                can_create = is_management_role(current_user.role)
                return render_template(
                        "work_s5.html",
                        audits=audits,
                        teams=teams,
                        team_labels=team_labels,
                        auditor_labels=auditor_labels,
                        default_items=DEFAULT_S5_ITEMS,
                        can_create=can_create,
                )


@login_required
@manager_required
@handle_errors
def work_5s_create():
        uow = new_uow()
        try:
                passed_ids = []
                for key in request.form:
                        if key.startswith("item_") and request.form.get(key) in ("1", "true", "on"):
                                index = int(key.split("_", 1)[1])
                                passed_ids.append(index)
                services.create_s5_audit(
                        uow,
                        current_user.id,
                        team_id=request.form.get("team_id"),
                        date=_optional_date(request.form.get("date")),
                        passed_ids=passed_ids,
                        notes=request.form.get("notes"),
                )
                flash("Auditoria 5S registrada.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_5s"))


@login_required
@manager_required
@handle_errors
def work_5s_delete(s5_audit_id):
        uow = new_uow()
        try:
                services.delete_s5_audit(uow, current_user.id, s5_audit_id)
                flash("Auditoria excluída.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_5s"))


def _culture_context(uow):
        all_teams = services.list_teams(uow)
        all_users = uow.users.list_all()
        team_labels = {team.team_id: team.name for team in all_teams}
        user_labels = {u.user_id: (u.profile.full_name or u.email) for u in all_users}
        users = sorted(all_users, key=lambda u: (u.profile.full_name or u.email).lower())
        return all_teams, team_labels, user_labels, users


def _scoped_team_list(uow, all_teams):
        from src.service_layer.permissions import scoped_team_ids
        scoped = set(scoped_team_ids(uow, current_user.id))
        return [t for t in all_teams if t.team_id in scoped]


@login_required
@handle_errors
def work_culture_wiki():
        uow = new_uow()
        with uow:
                articles = services.list_wiki_articles(uow, current_user.id)
                all_teams, team_labels, user_labels, users = _culture_context(uow)
                scoped_teams = _scoped_team_list(uow, all_teams)
                return render_template(
                        "work_culture_wiki.html",
                        articles=articles,
                        scoped_teams=scoped_teams,
                        team_labels=team_labels,
                        author_labels=user_labels,
                        user_role=current_user.role,
                )


@login_required
@handle_errors
def work_culture_wiki_create():
        uow = new_uow()
        try:
                team_id = request.form.get("team_id")
                if not team_id:
                        with uow:
                                team_id = uow.users.get_user_by_id(current_user.id).team_id or ""
                services.create_wiki_article(
                        uow,
                        current_user.id,
                        title=request.form.get("title"),
                        body=request.form.get("body"),
                        team_id=team_id or None,
                )
                flash("Artigo publicado.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_culture_wiki"))


@login_required
@handle_errors
def work_culture_wiki_update(wiki_article_id):
        uow = new_uow()
        try:
                title = request.form.get("title") or None
                body = request.form.get("body") or None
                services.update_wiki_article(uow, current_user.id, wiki_article_id, title=title, body=body)
                flash("Artigo atualizado.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_culture_wiki"))


@login_required
@handle_errors
def work_culture_wiki_delete(wiki_article_id):
        uow = new_uow()
        try:
                services.delete_wiki_article(uow, current_user.id, wiki_article_id)
                flash("Artigo excluído.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_culture_wiki"))


@login_required
@handle_errors
def work_culture_likes():
        uow = new_uow()
        with uow:
                kudos = services.list_kudos(uow, current_user.id)
                all_teams, team_labels, user_labels, users = _culture_context(uow)
                scoped_teams = _scoped_team_list(uow, all_teams)
                return render_template(
                        "work_culture_likes.html",
                        kudos=kudos,
                        scoped_teams=scoped_teams,
                        team_labels=team_labels,
                        user_labels=user_labels,
                        users=users,
                        current_user_id=current_user.id,
                        user_role=current_user.role,
                )


@login_required
@handle_errors
def work_culture_likes_create():
        uow = new_uow()
        try:
                team_id = request.form.get("team_id")
                if not team_id:
                        with uow:
                                team_id = uow.users.get_user_by_id(current_user.id).team_id or ""
                services.give_kudo(
                        uow,
                        current_user.id,
                        team_id=team_id or None,
                        receiver_id=request.form.get("receiver_id"),
                        message=request.form.get("message"),
                )
                flash("Like enviado.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_culture_likes"))


@login_required
@handle_errors
def work_culture_likes_delete(kudo_id):
        uow = new_uow()
        try:
                services.delete_kudo(uow, current_user.id, kudo_id)
                flash("Like excluído.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_culture_likes"))


@login_required
@handle_errors
def work_culture_events():
        uow = new_uow()
        with uow:
                events = services.list_team_events(uow, current_user.id)
                all_teams, team_labels, user_labels, users = _culture_context(uow)
                scoped_teams = _scoped_team_list(uow, all_teams)
                return render_template(
                        "work_culture_events.html",
                        events=events,
                        scoped_teams=scoped_teams,
                        team_labels=team_labels,
                        user_role=current_user.role,
                )


@login_required
@manager_required
@handle_errors
def work_culture_events_create():
        uow = new_uow()
        try:
                team_id = request.form.get("team_id")
                if not team_id:
                        with uow:
                                team_id = uow.users.get_user_by_id(current_user.id).team_id or ""
                services.create_team_event(
                        uow,
                        current_user.id,
                        team_id=team_id or None,
                        title=request.form.get("title"),
                        date=_optional_date(request.form.get("date")),
                        description=request.form.get("description"),
                )
                flash("Evento criado.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_culture_events"))


@login_required
@manager_required
@handle_errors
def work_culture_events_delete(event_id):
        uow = new_uow()
        try:
                services.delete_team_event(uow, current_user.id, event_id)
                flash("Evento excluído.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_culture_events"))


@login_required
@handle_errors
def work_exec():
        uow = new_uow()
        with uow:
                period_start = _optional_date(request.args.get("from"))
                period_end = _optional_date(request.args.get("to"))
                kpis = services.list_exec_kpis(uow, current_user.id, period_start=period_start, period_end=period_end)
                all_teams, team_labels, user_labels, users = _culture_context(uow)
                return render_template(
                        "work_exec.html",
                        kpis=kpis,
                        period_start=period_start,
                        period_end=period_end,
                        team_labels=team_labels,
                        user_labels=user_labels,
                )


@login_required
@handle_errors
def work_exec_team(team_id):
        uow = new_uow()
        with uow:
                kpis = [k for k in services.list_exec_kpis(uow, current_user.id) if k["team_id"] == team_id]
                if not kpis:
                        return redirect(url_for("work_exec"))
                team_kpi = kpis[0]
                from src.service_layer.permissions import scoped_team_ids
                if team_id not in set(scoped_team_ids(uow, current_user.id)):
                        return redirect(url_for("work_exec"))
                all_teams, team_labels, user_labels, users = _culture_context(uow)
                ideas = uow.users.list_ideas_by_team(team_id)
                implements = [i for i in ideas if i.status == "implemented"]
                return render_template(
                        "work_exec_team.html",
                        team_kpi=team_kpi,
                        team_labels=team_labels,
                        user_labels=user_labels,
                        accomplishments=uow.users.list_accomplishments_by_team(team_id),
                        ideas=ideas,
                        implemented_count=len(implements),
                        kudos=uow.users.list_kudos_by_team(team_id),
                        audits=uow.users.list_s5_audits_by_team(team_id),
                )