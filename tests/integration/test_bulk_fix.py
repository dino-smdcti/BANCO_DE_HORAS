import pytest
from unittest.mock import patch
from datetime import date

from werkzeug.security import generate_password_hash

from src.entrypoints.flask_app import app
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.domain.model import DailyPonto, PontoStatus, Team, User
from sqlalchemy import select

DAY_A = date(2026, 5, 4)
DAY_B = date(2026, 5, 5)


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


def _team(uow):
    with uow:
        team = Team(name="equipe_bulk")
        uow.session.add(team)
        uow.commit()
        return team.team_id


def _user(uow, email, role, team_id):
    with uow:
        user = User(email=email, password_hash=generate_password_hash("pass"), role=role, team_id=team_id)
        uow.session.add(user)
        uow.commit()
        return user.user_id


def _missing_entries(uow, emp):
    with uow:
        user = uow.users.get_user_by_id(emp)
        for day in (DAY_A, DAY_B):
            user.time_entries.append(DailyPonto(user_id=emp, entry_date=day, status=PontoStatus.MISSING, has_lunch_break=True))
        uow.commit()


def _login(client, uid):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)


def test_bulk_fix_corrects_selected_days_only(client, uow):
    team = _team(uow)
    mgr = _user(uow, "mgr_bulk@test.com", "manager", team)
    emp = _user(uow, "emp_bulk@test.com", "employee", team)
    _missing_entries(uow, emp)
    _login(client, mgr)
    response = client.post(f"/manager/bulk-fix-ponto/{emp}", data={
        "dates": [DAY_A.isoformat(), DAY_B.isoformat()],
        "selected_points": [DAY_A.isoformat()],
        f"arrival_{DAY_A.isoformat()}": "08:00",
        f"departure_{DAY_A.isoformat()}": "17:00",
        f"arrival_{DAY_B.isoformat()}": "",
        f"departure_{DAY_B.isoformat()}": "",
    })
    assert response.status_code == 302
    with uow:
        user = uow.users.get_user_by_id(emp)
        entries = {p.entry_date: p for p in user.time_entries}
        assert entries[DAY_A].arrival.strftime("%H:%M") == "08:00"
        assert entries[DAY_A].departure.strftime("%H:%M") == "17:00"
        assert entries[DAY_A].status == PontoStatus.CORRECTED
        assert entries[DAY_B].status == PontoStatus.MISSING


def test_bulk_fix_cross_team_denied(client, uow):
    team_a = _team(uow)
    with uow:
        team_b = Team(name="equipe_bulk_b")
        uow.session.add(team_b)
        uow.commit()
        team_b_id = team_b.team_id
    mgr = _user(uow, "mgr_bulk2@test.com", "manager", team_a)
    emp = _user(uow, "emp_bulk2@test.com", "employee", team_b_id)
    _login(client, mgr)
    response = client.post(f"/manager/bulk-fix-ponto/{emp}", data={
        "dates": [DAY_A.isoformat()],
        "selected_points": [DAY_A.isoformat()],
        f"arrival_{DAY_A.isoformat()}": "08:00",
        f"departure_{DAY_A.isoformat()}": "17:00",
    })
    assert response.status_code == 302
    assert "dashboard" in response.headers.get("Location", "")