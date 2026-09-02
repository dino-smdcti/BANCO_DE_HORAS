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
        app.add_url_rule("/work/culture/mentoring", "work_culture_mentoring", work_culture_mentoring)
        app.add_url_rule("/work/culture/mentoring/create", "work_culture_mentoring_create", work_culture_mentoring_create, methods=["POST"])
        app.add_url_rule("/work/culture/mentoring/<int:mentorship_id>/end", "work_culture_mentoring_end", work_culture_mentoring_end, methods=["POST"])
        app.add_url_rule("/work/culture/mentoring/<int:mentorship_id>/delete", "work_culture_mentoring_delete", work_culture_mentoring_delete, methods=["POST"])
        app.add_url_rule("/work/culture/kudos", "work_culture_kudos", work_culture_kudos)
        app.add_url_rule("/work/culture/kudos/create", "work_culture_kudos_create", work_culture_kudos_create, methods=["POST"])
        app.add_url_rule("/work/culture/kudos/<int:kudo_id>/delete", "work_culture_kudos_delete", work_culture_kudos_delete, methods=["POST"])
        app.add_url_rule("/work/culture/events", "work_culture_events", work_culture_events)
        app.add_url_rule("/work/culture/events/create", "work_culture_events_create", work_culture_events_create, methods=["POST"])
        app.add_url_rule("/work/culture/events/<int:event_id>/delete", "work_culture_events_delete", work_culture_events_delete, methods=["POST"])


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
                return render_template(
                        "work_accomplishments.html",
                        accomplishments=accomplishments,
                        teams=managed,
                        users=users,
                        team_labels=team_labels,
                        user_labels=user_labels,
                        user_role=current_user.role,
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
                        achieved_by_user_id=request.form.get("achieved_by_user_id") or None,
                )
                flash("Conquista registrada.", "success")
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
                        achieved_by_user_id=request.form.get("achieved_by_user_id") or None,
                        clear_end_date=request.form.get("clear_end_date") in ("1", "true", "on"),
                )
                flash("Conquista atualizada.", "success")
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
                flash("Conquista excluída.", "success")
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
def work_culture_mentoring():
        uow = new_uow()
        with uow:
                pairs = services.list_mentorships(uow, current_user.id)
                all_teams, team_labels, user_labels, users = _culture_context(uow)
                scoped_teams = _scoped_team_list(uow, all_teams)
                return render_template(
                        "work_culture_mentoring.html",
                        pairs=pairs,
                        scoped_teams=scoped_teams,
                        team_labels=team_labels,
                        user_labels=user_labels,
                        users=users,
                        user_role=current_user.role,
                )


@login_required
@manager_required
@handle_errors
def work_culture_mentoring_create():
        uow = new_uow()
        try:
                services.create_mentorship(
                        uow,
                        current_user.id,
                        team_id=request.form.get("team_id"),
                        mentor_id=request.form.get("mentor_id"),
                        mentee_id=request.form.get("mentee_id"),
                        start_date=_optional_date(request.form.get("start_date")),
                )
                flash("Mentoria criada.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_culture_mentoring"))


@login_required
@manager_required
@handle_errors
def work_culture_mentoring_end(mentorship_id):
        uow = new_uow()
        try:
                services.end_mentorship(uow, current_user.id, mentorship_id)
                flash("Mentoria encerrada.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_culture_mentoring"))


@login_required
@manager_required
@handle_errors
def work_culture_mentoring_delete(mentorship_id):
        uow = new_uow()
        try:
                services.delete_mentorship(uow, current_user.id, mentorship_id)
                flash("Mentoria excluída.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_culture_mentoring"))


@login_required
@handle_errors
def work_culture_kudos():
        uow = new_uow()
        with uow:
                kudos = services.list_kudos(uow, current_user.id)
                all_teams, team_labels, user_labels, users = _culture_context(uow)
                scoped_teams = _scoped_team_list(uow, all_teams)
                return render_template(
                        "work_culture_kudos.html",
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
def work_culture_kudos_create():
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
                flash("Kudos enviado.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_culture_kudos"))


@login_required
@handle_errors
def work_culture_kudos_delete(kudo_id):
        uow = new_uow()
        try:
                services.delete_kudo(uow, current_user.id, kudo_id)
                flash("Kudos excluído.", "success")
        except (ValueError, PermissionError) as error:
                flash(str(error), "danger")
        return redirect(url_for("work_culture_kudos"))


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