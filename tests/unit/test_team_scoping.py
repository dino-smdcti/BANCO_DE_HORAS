from datetime import date, time

import pytest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.domain.model import CorrectionRequest, Team
from src.service_layer import services
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.user_service import register_user


def _session_uow():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    start_mappers()
    return SqlAlchemyUnitOfWork(session_factory)


def _register(uow, email, role):
    with uow:
        register_user(uow, email, "pass", role)
        return uow.users.get_user_by_email(email).user_id


def _make_team(uow, name="Equipe"):
    with uow:
        team = Team(name=name)
        uow.session.add(team)
        uow.commit()
        return team.team_id


def _set_team(uow, user_id, team_id):
    with uow:
        user = uow.users.get_user_by_id(user_id)
        user.team_id = team_id
        uow.commit()


def _scenario():
    uow = _session_uow()
    mgr = _register(uow, "mgrx@test.com", "manager")
    emp = _register(uow, "empx@test.com", "employee")
    team_a = _make_team(uow, "Equipe A")
    team_b = _make_team(uow, "Equipe B")
    return uow, mgr, emp, team_a, team_b


def test_add_vacation_cross_team_denied():
    uow, mgr, emp, team_a, team_b = _scenario()
    _set_team(uow, mgr, team_a)
    _set_team(uow, emp, team_b)
    with pytest.raises(PermissionError):
        services.add_vacation(uow, mgr, emp, date(2026, 1, 5), date(2026, 1, 9))


def test_add_vacation_same_team_allowed():
    uow, mgr, emp, team_a, _ = _scenario()
    _set_team(uow, mgr, team_a)
    _set_team(uow, emp, team_a)
    services.add_vacation(uow, mgr, emp, date(2026, 1, 5), date(2026, 1, 9))
    with uow:
        target = uow.users.get_user_by_id(emp)
        assert any(v.start_date == date(2026, 1, 5) for v in target.vacations)


def test_manual_ponto_correction_cross_team_denied():
    uow, mgr, emp, team_a, team_b = _scenario()
    _set_team(uow, mgr, team_a)
    _set_team(uow, emp, team_b)
    with pytest.raises(PermissionError):
        services.manual_ponto_correction(uow, mgr, emp, date(2026, 1, 5), time(9, 0))


def test_delete_user_cross_team_denied():
    uow, mgr, emp, team_a, team_b = _scenario()
    _set_team(uow, mgr, team_a)
    _set_team(uow, emp, team_b)
    with pytest.raises(PermissionError):
        services.delete_user(uow, mgr, emp)


def test_set_schedule_cross_team_denied():
    uow, mgr, emp, team_a, team_b = _scenario()
    _set_team(uow, mgr, team_a)
    _set_team(uow, emp, team_b)
    with pytest.raises(PermissionError):
        services.set_work_schedule(uow, mgr, emp, time(9, 0), None, None, time(18, 0))


def test_retroactive_logs_cross_team_denied():
    uow, mgr, emp, team_a, team_b = _scenario()
    _set_team(uow, mgr, team_a)
    _set_team(uow, emp, team_b)
    with pytest.raises(PermissionError):
        services.complete_retroactive_logs(uow, mgr, emp, date(2026, 1, 10), False)


def test_visible_employees_scoped_by_team():
    uow = _session_uow()
    admin = _register(uow, "admz@test.com", "admin")
    mgr = _register(uow, "mgrz@test.com", "manager")
    emp_a = _register(uow, "empa@test.com", "employee")
    emp_b = _register(uow, "empb@test.com", "employee")
    team_a = _make_team(uow, "Equipe A")
    team_b = _make_team(uow, "Equipe B")
    _set_team(uow, mgr, team_a)
    _set_team(uow, emp_a, team_a)
    _set_team(uow, emp_b, team_b)

    with uow:
        manager_visible = services.get_all_employees(uow, requester_id=mgr)
        assert {u.user_id for u in manager_visible} == {mgr, emp_a}

        admin_visible = services.get_all_employees(uow, requester_id=admin)
        assert {u.user_id for u in admin_visible} == {admin, mgr, emp_a, emp_b}


def test_visible_employees_manager_without_team_sees_nobody():
    uow = _session_uow()
    mgr = _register(uow, "mgrz2@test.com", "manager")
    emp = _register(uow, "empz2@test.com", "employee")
    with uow:
        assert services.get_all_employees(uow, requester_id=mgr) == []
        assert {u.user_id for u in services.get_all_employees(uow, requester_id=emp)} == {emp}


def test_pending_corrections_scoped_to_team():
    uow = _session_uow()
    admin = _register(uow, "admc@test.com", "admin")
    mgr = _register(uow, "mgrc@test.com", "manager")
    emp_a = _register(uow, "empac@test.com", "employee")
    emp_b = _register(uow, "empbc@test.com", "employee")
    team_a = _make_team(uow, "Equipe A")
    team_b = _make_team(uow, "Equipe B")
    _set_team(uow, mgr, team_a)
    _set_team(uow, emp_a, team_a)
    _set_team(uow, emp_b, team_b)

    services.submit_correction_request(uow, emp_a, date(2026, 1, 5), "Chegada", time(9, 0))
    services.submit_correction_request(uow, emp_b, date(2026, 1, 6), "Chegada", time(10, 0))

    with uow:
        pending = services.list_pending_corrections(uow, mgr)
        assert [r.user_id for r in pending] == [emp_a]

        pending_admin = services.list_pending_corrections(uow, admin)
        assert {r.user_id for r in pending_admin} == {emp_a, emp_b}


def test_review_correction_request_cross_team_denied():
    uow = _session_uow()
    mgr = _register(uow, "mgrd@test.com", "manager")
    emp = _register(uow, "empd@test.com", "employee")
    team_a = _make_team(uow, "Equipe A")
    team_b = _make_team(uow, "Equipe B")
    _set_team(uow, mgr, team_a)
    _set_team(uow, emp, team_b)

    services.submit_correction_request(uow, emp, date(2026, 1, 6), "Chegada", time(10, 0))
    with uow:
        request_id = uow.session.execute(select(CorrectionRequest)).scalars().first().request_id
    with pytest.raises(PermissionError):
        services.review_correction_request(uow, mgr, request_id, True)