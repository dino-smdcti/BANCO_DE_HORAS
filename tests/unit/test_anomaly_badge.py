from datetime import date, time

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.domain.model import DailyPonto, PontoStatus, Team
from src.service_layer import services
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.user_service import register_user

DAY = date(2026, 5, 4)


def _session_uow():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    start_mappers()
    return SqlAlchemyUnitOfWork(session_factory)


def _register(uow, email, role):
    with uow:
        register_user(uow, email, "pass", role)
        return uow.users.get_user_by_email(email).user_id


def _team_for(uow, mgr, emp):
    with uow:
        team = Team(name="equipe_badge")
        uow.session.add(team)
        uow.commit()
        uow.users.get_user_by_id(mgr).team_id = team.team_id
        uow.users.get_user_by_id(emp).team_id = team.team_id
        uow.commit()


def _ponto_with_anomaly(uow, emp):
    with uow:
        user = uow.users.get_user_by_id(emp)
        user.time_entries.append(DailyPonto(
            user_id=emp, entry_date=DAY, arrival=time(9, 30),
            status=PontoStatus.LATE, arrival_late=True, has_lunch_break=True,
        ))
        uow.commit()


def _scenario():
    uow = _session_uow()
    adm = _register(uow, "adm_badge@test.com", "admin")
    emp = _register(uow, "emp_badge@test.com", "employee")
    mgr = _register(uow, "mgr_badge@test.com", "manager")
    _team_for(uow, mgr, emp)
    _ponto_with_anomaly(uow, emp)
    return uow, adm, mgr, emp


def _reload_ponto(uow, emp, day=DAY):
    with uow:
        user = uow.users.get_user_by_id(emp)
        for p in user.time_entries:
            if p.entry_date == day:
                return p
        return None


def test_approve_arrival_anomaly_sets_approved_flag():
    uow, adm, _, emp = _scenario()
    services.review_anomaly_badge(uow, adm, emp, DAY, "arrival", "approve")
    ponto = _reload_ponto(uow, emp)
    assert ponto.arrival_late_reviewed is True
    assert ponto.arrival_late_approved is True
    assert ponto.arrival_late_excused is False
    assert ponto.has_anomaly is False


def test_excuse_arrival_anomaly_sets_excused_flag():
    uow, adm, _, emp = _scenario()
    services.review_anomaly_badge(uow, adm, emp, DAY, "arrival", "excuse")
    ponto = _reload_ponto(uow, emp)
    assert ponto.arrival_late_reviewed is True
    assert ponto.arrival_late_excused is True
    assert ponto.has_anomaly is False


def test_excuse_missing_anomaly():
    uow = _session_uow()
    adm = _register(uow, "adm_badge2@test.com", "admin")
    emp = _register(uow, "emp_badge2@test.com", "employee")
    mgr = _register(uow, "mgr_badge2@test.com", "manager")
    _team_for(uow, mgr, emp)
    with uow:
        user = uow.users.get_user_by_id(emp)
        user.time_entries.append(DailyPonto(user_id=emp, entry_date=DAY, status=PontoStatus.MISSING, has_lunch_break=True))
        uow.commit()
    services.review_anomaly_badge(uow, adm, emp, DAY, "missing", "excuse")
    ponto = _reload_ponto(uow, emp)
    assert ponto.missing_reviewed is True
    assert ponto.missing_excused is True
    assert ponto.has_anomaly is False


def test_denies_manager_and_employee_actors():
    uow, _, mgr, emp = _scenario()
    with pytest.raises(PermissionError):
        services.review_anomaly_badge(uow, mgr, emp, DAY, "arrival", "approve")
    outsider = _register(uow, "emp_badge3@test.com", "employee")
    with pytest.raises(PermissionError):
        services.review_anomaly_badge(uow, outsider, emp, DAY, "arrival", "approve")


def test_unknown_stage_is_rejected():
    uow, adm, _, emp = _scenario()
    with pytest.raises(KeyError):
        services.review_anomaly_badge(uow, adm, emp, DAY, "bogus", "approve")


def test_missing_ponto_raises_value_error():
    uow, adm, _, emp = _scenario()
    with pytest.raises(ValueError):
        services.review_anomaly_badge(uow, adm, emp, date(2026, 5, 5), "arrival", "approve")