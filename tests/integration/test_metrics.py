"""Integration tests for the filterable per-employee metrics panel and bulk report."""
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
        team = uow.session.execute(select(Team).where(Team.name == "__metrics_default__")).scalar_one_or_none()
        if team is None:
            team = Team(name="__metrics_default__")
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
        services.set_work_schedule(uow, uid, uid, time(8, 0), time(12, 0), time(13, 0), time(17, 0))
        uow.commit()
        return uid


def _login(client, uid):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)


def test_metrics_panel_renders_for_admin(client, uow):
    admin = _create_user(uow, "adm_met@test.com", role="admin")
    _login(client, admin)
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "Métricas".encode("utf-8") in r.data


def test_metrics_panel_forbidden_for_employee(client, uow):
    emp = _create_user(uow, "emp_met@test.com")
    _login(client, emp)
    r = client.get("/metrics", follow_redirects=False)
    assert r.status_code == 302


def test_bulk_report_exports_xlsx(client, uow):
    admin = _create_user(uow, "adm_met2@test.com", role="admin")
    _login(client, admin)
    r = client.get("/report/bulk")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers.get("Content-Type", "")


def test_compute_period_metrics_counts_worked_and_balance(uow):
    emp = _create_user(uow, "emp_met_calc@test.com")
    with uow:
        user = uow.users.get_user_by_id(emp)
        user.time_entries.append(DailyPonto(
            user_id=emp,
            entry_date=date(2026, 5, 4),
            arrival=time(8, 0),
            lunch_start=time(12, 0),
            lunch_end=time(13, 0),
            departure=time(18, 0),  # +1h overtime
            status=PontoStatus.ON_TIME,
        ))
        uow.commit()
        user = uow.users.get_user_by_id(emp)
        metrics = services.compute_period_metrics(user, date(2026, 5, 1), date(2026, 5, 31))
    assert metrics["worked_minutes"] == 540
    assert metrics["expected_minutes"] == 480
    assert metrics["balance_minutes"] == 60


def test_metrics_filters_by_employee(client, uow):
    admin = _create_user(uow, "adm_met3@test.com", role="admin")
    emp_a = _create_user(uow, "emp_met_a@test.com")
    emp_b = _create_user(uow, "emp_met_b@test.com")
    _login(client, admin)
    r = client.get(f"/metrics?employee_id={emp_b}")
    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert "emp_met_b@test.com" in body


def test_list_clocking_users_filters_by_team(uow):
    _create_user(uow, "adm_met4@test.com", role="admin")
    emp = _create_user(uow, "emp_met_team@test.com")
    with uow:
        users = services.list_clocking_users(uow, team_id=None)
        emp_user = uow.users.get_user_by_id(emp)
        team_id = emp_user.team_id
        scoped = services.list_clocking_users(uow, team_id=team_id)
        assert emp in [u.user_id for u in scoped]
        assert len(scoped) <= len(users)
