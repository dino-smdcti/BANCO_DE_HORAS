"""Integration tests for the anomaly justification flow.

Employee submits a justification for a late/missing day; a manager can then
approve (JUSTIFIED), reject (LATE/REJECTED) or archive (DISMISSED) it.
"""
import pytest
from datetime import date, time
from unittest.mock import patch

from src.entrypoints.flask_app import app
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer import services
from src.domain.model import DailyPonto, PontoStatus, Team, User
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


def _default_team(uow):
    with uow:
        from sqlalchemy import select
        team = uow.session.execute(select(Team).where(Team.name == "__just_default__")).scalar_one_or_none()
        if team is None:
            team = Team(name="__just_default__")
            uow.session.add(team)
            uow.commit()
        return team.team_id


def _create_user(uow, email, role="employee"):
    with uow:
        user = User(email=email, password_hash=generate_password_hash("pass"), role=role)
        uow.session.add(user)
        uow.commit()
        uid = user.user_id
        user.team_id = _default_team(uow)
        uow.commit()
        return uid


def _login(client, uid):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)


def _late_ponto(uow, user_id, entry_date):
    with uow:
        user = uow.users.get_user_by_id(user_id)
        ponto = DailyPonto(
            user_id=user_id,
            entry_date=entry_date,
            arrival=time(9, 0),
            status=PontoStatus.LATE,
            arrival_late=True,
        )
        user.time_entries.append(ponto)
        uow.commit()


def test_employee_submits_justification(client, uow):
    emp = _create_user(uow, "emp_just@test.com")
    _late_ponto(uow, emp, date(2026, 5, 4))
    _login(client, emp)
    r = client.post("/submit-justification", data={"entry_date": "2026-05-04", "justification": "Trânsito na ponte"}, follow_redirects=False)
    assert r.status_code == 302
    with uow:
        user = uow.users.get_user_by_id(emp)
        ponto = next(p for p in user.time_entries if p.entry_date == date(2026, 5, 4))
        assert ponto.justification == "Trânsito na ponte"
        assert ponto.status == PontoStatus.LATE  # still pending review


def test_manager_approves_justification(client, uow):
    mgr = _create_user(uow, "mgr_just@test.com", role="manager")
    emp = _create_user(uow, "emp_just_appr@test.com")
    _late_ponto(uow, emp, date(2026, 5, 5))
    services.submit_justification(uow, emp, date(2026, 5, 5), "Consulta médica")
    _login(client, mgr)
    r = client.post(f"/manager/review-justification/{emp}/2026-05-05", data={"action": "approve"}, follow_redirects=False)
    assert r.status_code == 302
    with uow:
        user = uow.users.get_user_by_id(emp)
        ponto = next(p for p in user.time_entries if p.entry_date == date(2026, 5, 5))
        assert ponto.status == PontoStatus.JUSTIFIED


def test_manager_rejects_justification(client, uow):
    mgr = _create_user(uow, "mgr_just2@test.com", role="manager")
    emp = _create_user(uow, "emp_just_rej@test.com")
    _late_ponto(uow, emp, date(2026, 5, 6))
    services.submit_justification(uow, emp, date(2026, 5, 6), "Dormi demais")
    _login(client, mgr)
    r = client.post(f"/manager/review-justification/{emp}/2026-05-06", data={"action": "reject"}, follow_redirects=False)
    assert r.status_code == 302
    with uow:
        user = uow.users.get_user_by_id(emp)
        ponto = next(p for p in user.time_entries if p.entry_date == date(2026, 5, 6))
        assert ponto.status == PontoStatus.LATE
        assert ponto.justification is None


def test_employee_justification_appears_in_manager_card(client, uow):
    mgr = _create_user(uow, "mgr_just3@test.com", role="manager")
    emp = _create_user(uow, "emp_just_card@test.com")
    _late_ponto(uow, emp, date(2026, 5, 7))
    services.submit_justification(uow, emp, date(2026, 5, 7), "Reunião externa")
    _login(client, mgr)
    body = client.get("/management").data.decode("utf-8")
    assert "Reunião externa" in body


def test_archived_justification_is_listed(client, uow):
    mgr = _create_user(uow, "mgr_just4@test.com", role="manager")
    emp = _create_user(uow, "emp_just_arch@test.com")
    _late_ponto(uow, emp, date(2026, 5, 8))
    services.submit_justification(uow, emp, date(2026, 5, 8), "Atestado")
    services.dismiss_justification(uow, mgr, emp, date(2026, 5, 8))
    _login(client, mgr)
    body = client.get("/manager/archived-justifications").data.decode("utf-8")
    assert "Atestado" in body
