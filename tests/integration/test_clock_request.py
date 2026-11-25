"""Integration tests for the pre-approval clock request flow.

An employee asks their superior in advance to accept a late/early clock; once
approved, the clock service auto-excuses the anomaly instead of flagging it.
"""
import pytest
from datetime import date, time
from unittest.mock import patch

from sqlalchemy import select

from src.entrypoints.flask_app import app
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer import services
from src.service_layer.clock_request_service import has_approved_clock_request
from src.domain.model import ClockRequest, DailyPonto, PontoStatus, Team, User
from werkzeug.security import generate_password_hash


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


def _make_team_with_lead(uow, lead_id):
    with uow:
        team = Team(name=f"team_{lead_id}", lead_user_id=lead_id)
        uow.session.add(team)
        uow.commit()
        return team.team_id


def _create_user(uow, email, role="employee", team_id=None):
    with uow:
        user = User(email=email, password_hash=generate_password_hash("pass"), role=role, team_id=team_id)
        uow.session.add(user)
        uow.commit()
        services.set_work_schedule(uow, user.user_id, user.user_id, time(8, 0), time(12, 0), time(13, 0), time(17, 0))
        uow.commit()
        return user.user_id


def _login(client, uid):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)


def test_employee_creates_clock_request_and_manager_approves(client, uow):
    mgr = _create_user(uow, "mgr_cr@test.com", role="manager")
    team_id = _make_team_with_lead(uow, mgr)
    emp = _create_user(uow, "emp_cr@test.com", team_id=team_id)

    _login(client, emp)
    r = client.post("/clock-request", data={
        "entry_date": "2026-05-10", "stage": "arrival", "direction": "later",
        "proposed_time": "09:00", "reason": "consulta médica",
    }, follow_redirects=False)
    assert r.status_code == 302

    with uow:
        request = uow.session.execute(select(ClockRequest)).scalars().first()
        assert request is not None
        assert request.user_id == emp
        assert request.status == "pending"
        request_id = request.request_id

    _login(client, mgr)
    r = client.post(f"/clock-request/{request_id}/review", data={"action": "approve"}, follow_redirects=False)
    assert r.status_code == 302

    with uow:
        assert has_approved_clock_request(uow, emp, date(2026, 5, 10), "arrival")


def test_manager_rejects_clock_request(client, uow):
    mgr = _create_user(uow, "mgr_cr2@test.com", role="manager")
    team_id = _make_team_with_lead(uow, mgr)
    emp = _create_user(uow, "emp_cr2@test.com", team_id=team_id)
    services.create_clock_request(uow, emp, date(2026, 5, 11), "departure", "earlier", time(16, 0), "compromisso")

    with uow:
        request_id = uow.session.execute(select(ClockRequest)).scalars().first().request_id

    _login(client, mgr)
    r = client.post(f"/clock-request/{request_id}/review", data={"action": "reject", "reviewer_notes": "sem justificativa"}, follow_redirects=False)
    assert r.status_code == 302

    with uow:
        assert not has_approved_clock_request(uow, emp, date(2026, 5, 11), "departure")


def test_approved_request_auto_excuses_late_arrival(uow):
    mgr = _create_user(uow, "mgr_cr3@test.com", role="manager")
    team_id = _make_team_with_lead(uow, mgr)
    emp = _create_user(uow, "emp_cr3@test.com", team_id=team_id)

    services.create_clock_request(uow, emp, date(2026, 5, 12), "arrival", "later", time(9, 0), "consulta")
    with uow:
        request_id = uow.session.execute(select(ClockRequest)).scalars().first().request_id
    services.review_clock_request(uow, mgr, request_id, True)

    with uow:
        user = uow.users.get_user_by_id(emp)
        ponto = DailyPonto(user_id=emp, entry_date=date(2026, 5, 12))
        user.time_entries.append(ponto)
        uow.commit()
        user = uow.users.get_user_by_id(emp)
        ponto = next(p for p in user.time_entries if p.entry_date == date(2026, 5, 12))
        from src.service_layer.clock_service import _flag_if_arrival_late
        _flag_if_arrival_late(uow, ponto, user, date(2026, 5, 12), time(9, 0))
        assert ponto.arrival_late_approved
        assert not ponto.arrival_late
        assert ponto.status != PontoStatus.LATE
