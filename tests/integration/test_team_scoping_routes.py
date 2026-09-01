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