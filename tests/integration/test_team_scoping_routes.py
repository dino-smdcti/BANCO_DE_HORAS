import pytest
from unittest.mock import patch
from datetime import date

from werkzeug.security import generate_password_hash

from src.entrypoints.flask_app import app
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.domain.model import User, Team
from sqlalchemy import select


@pytest.fixture
def client(session_factory):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    patcher = patch("src.entrypoints.flask_app.process_daily_absences", lambda uow: None)
    patcher.start()
    with patch("src.entrypoints.flask_app.SqlAlchemyUnitOfWork", lambda: SqlAlchemyUnitOfWork(session_factory)):
        with app.test_client() as c:
            yield c
    patcher.stop()


def _make_user(uow, email, role, team_id=None):
    with uow:
        user = User(email=email, password_hash=generate_password_hash("pass"), role=role, team_id=team_id)
        uow.session.add(user)
        uow.commit()
        return user.user_id


def _make_team(uow, name):
    with uow:
        team = Team(name=name)
        uow.session.add(team)
        uow.commit()
        return team.team_id


def _login(client, uid):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)


def _redirect_target(response):
    return response.headers.get("Location")


class TestRouteTeamScoping:
    def test_manager_cannot_view_other_team_logs(self, client, uow):
        team_a = _make_team(uow, "Equipe A")
        team_b = _make_team(uow, "Equipe B")
        mgr = _make_user(uow, "mgr_sc@test.com", "manager", team_a)
        emp_b = _make_user(uow, "empb_sc@test.com", "employee", team_b)
        _login(client, mgr)
        response = client.get(f"/manager/view-logs/{emp_b}")
        assert response.status_code == 302
        assert "dashboard" in _redirect_target(response) or "complete-profile" in _redirect_target(response)

    def test_manager_can_view_own_team_logs(self, client, uow):
        team_a = _make_team(uow, "Equipe A")
        mgr = _make_user(uow, "mgr_sc2@test.com", "manager", team_a)
        emp_a = _make_user(uow, "empa_sc2@test.com", "employee", team_a)
        _login(client, mgr)
        response = client.get(f"/manager/view-logs/{emp_a}")
        assert response.status_code == 200

    def test_admin_can_view_any_team_logs(self, client, uow):
        team_a = _make_team(uow, "Equipe A")
        team_b = _make_team(uow, "Equipe B")
        adm = _make_user(uow, "adm_sc@test.com", "admin")
        emp_b = _make_user(uow, "empb_sc2@test.com", "employee", team_b)
        _login(client, adm)
        response = client.get(f"/manager/view-logs/{emp_b}")
        assert response.status_code == 200

    def test_manager_mutation_denied_for_other_team(self, client, uow):
        team_a = _make_team(uow, "Equipe A")
        team_b = _make_team(uow, "Equipe B")
        mgr = _make_user(uow, "mgr_sc3@test.com", "manager", team_a)
        emp_b = _make_user(uow, "empb_sc3@test.com", "employee", team_b)
        _login(client, mgr)
        response = client.post(f"/manager/delete-ponto/{emp_b}/{date(2026, 5, 4).isoformat()}")
        assert response.status_code == 302
        assert "dashboard" in _redirect_target(response) or "complete-profile" in _redirect_target(response)


class TestTeamAdminRoutes:
    def test_team_page_requires_admin_role(self, client, uow):
        team = _make_team(uow, "Equipe A")
        emp = _make_user(uow, "emp_admin_deny@test.com", "employee", team)
        _login(client, emp)
        response = client.get("/admin/teams")
        assert response.status_code == 302
        assert "dashboard" in _redirect_target(response) or "complete-profile" in _redirect_target(response)

    def test_team_page_allows_admin_and_gestor(self, client, uow):
        for role in ("admin", "gestor"):
            user = _make_user(uow, f"{role}_page@test.com", role)
            _login(client, user)
            response = client.get("/admin/teams")
            assert response.status_code == 200

    def test_create_team_flow(self, client, uow):
        adm = _make_user(uow, "adm_create@test.com", "admin")
        _login(client, adm)
        response = client.post("/admin/teams/create", data={"name": "Equipe Nova", "secretariat": "SMDCTI"})
        assert response.status_code == 302
        with uow:
            teams = uow.session.execute(select(Team)).scalars().all()
            assert [t.name for t in teams] == ["Equipe Nova"]

    def test_assign_team_flow(self, client, uow):
        adm = _make_user(uow, "adm_assign@test.com", "admin")
        emp = _make_user(uow, "emp_assign_route@test.com", "employee")
        team_id = _make_team(uow, "Equipe Alvo")
        _login(client, adm)
        response = client.post("/admin/teams/assign", data={"user_id": emp, "team_id": team_id})
        assert response.status_code == 302
        with uow:
            assert uow.users.get_user_by_id(emp).team_id == team_id

    def test_assign_team_can_unassign(self, client, uow):
        adm = _make_user(uow, "adm_unassign@test.com", "admin")
        team_id = _make_team(uow, "Equipe Alvo")
        emp = _make_user(uow, "emp_unassign@test.com", "employee", team_id)
        _login(client, adm)
        response = client.post("/admin/teams/assign", data={"user_id": emp, "team_id": ""})
        assert response.status_code == 302
        with uow:
            assert uow.users.get_user_by_id(emp).team_id is None


class TestUserDeactivation:
    def test_deactivate_keeps_workforce_history_and_row(self, client, uow):
        # Deleting a user must soft-deactivate, not hard-delete, so workforce
        # FKs (tasks created by this user) survive and history stays intact.
        team_id = _make_team(uow, "Time Vivo")
        mgr = _make_user(uow, "mgr_deact@test.com", "manager", team_id)
        emp = _make_user(uow, "emp_deact@test.com", "employee", team_id)
        with uow:
            from src.domain.model import TeamTask
            task = TeamTask(team_id=team_id, title="Tarefa resiliente", created_by=emp)
            uow.session.add(task)
            uow.commit()
            task_id = task.task_id
        _login(client, mgr)
        response = client.post(f"/manager/delete-user/{emp}")
        assert response.status_code in (200, 302)
        with uow:
            kept = uow.users.get_user_by_id(emp)
            assert kept is not None
            assert kept.is_active is False
            saved = uow.users.get_task_by_id(task_id)
            assert saved is not None and saved.created_by == emp

    def test_deactivated_user_cannot_log_in(self, client, uow):
        team_id = _make_team(uow, "Time Bloqueio")
        mgr = _make_user(uow, "mgr_blk@test.com", "manager", team_id)
        emp = _make_user(uow, "emp_blk@test.com", "employee", team_id)
        with uow:
            user = uow.users.get_user_by_id(emp)
            user.password_set = True
            user.password_hash = generate_password_hash("secret-pass")
            user.is_active = False
            uow.commit()
        r = client.post("/login", data={"email": "emp_blk@test.com", "password": "secret-pass"}, follow_redirects=True)
        body = r.data.decode("utf-8")
        assert "E-mail ou senha inválidos" in body

    def test_team_rename_preserves_history_by_team_id(self, client, uow):
        team_id = _make_team(uow, "Nome Antigo")
        mgr = _make_user(uow, "mgr_rename@test.com", "manager", team_id)
        with uow:
            from src.domain.model import TeamTask
            task = TeamTask(team_id=team_id, title="Marca do time", created_by=mgr)
            uow.session.add(task)
            uow.commit()
        with uow:
            from src.service_layer.team_service import scoped_update_team
            scoped_update_team(uow, mgr, team_id, name="Nome Novo")
        with uow:
            team = uow.users.get_team_by_id(team_id)
            assert team.name == "Nome Novo"
            # History re-resolves by team_id, so the renamed team still owns the task.
            assert any(t.title == "Marca do time" for t in uow.users.list_tasks_by_team(team_id))

    def test_manager_scopes_to_own_team_without_lead(self, client, uow):
        # A team with no lead_user_id must still scope a member-manager to it.
        team_id = _make_team(uow, "Sem Lider")
        mgr = _make_user(uow, "mgr_nolead@test.com", "manager", team_id)
        with uow:
            team = uow.users.get_team_by_id(team_id)
            assert team.lead_user_id is None
            from src.service_layer.permissions import scoped_team_ids
            assert scoped_team_ids(uow, mgr) == [team_id]