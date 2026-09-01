from datetime import date, time

import pytest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.domain.model import CorrectionRequest, DailyPonto, Team
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
        team = Team(name="equipe_correcao")
        uow.session.add(team)
        uow.commit()
        for uid in (mgr, emp):
            uow.users.get_user_by_id(uid).team_id = team.team_id
        uow.commit()
        return team.team_id


def _setup_schedule(uow, uid):
    services.set_work_schedule(uow, uid, uid, time(8, 0), time(12, 0), time(13, 0), time(17, 0))


def _manual_ponto(uow, uid):
    with uow:
        user = uow.users.get_user_by_id(uid)
        user.time_entries.append(DailyPonto(user_id=uid, entry_date=DAY, arrival=time(9, 0), has_lunch_break=True))
        uow.commit()


def _first_request_id(uow):
    with uow:
        return uow.session.execute(select(CorrectionRequest)).scalars().first().request_id


def _correction_scenario():
    uow = _session_uow()
    mgr = _register(uow, "mgr_cor@test.com", "manager")
    emp = _register(uow, "emp_cor@test.com", "employee")
    _team_for(uow, mgr, emp)
    _setup_schedule(uow, emp)
    _manual_ponto(uow, emp)
    return uow, mgr, emp


def test_submit_creates_pending_request_visible_to_manager():
    uow, mgr, emp = _correction_scenario()
    services.submit_correction_request(uow, emp, DAY, "arrival", time(8, 30))
    with uow:
        pending = services.list_pending_corrections(uow, mgr)
        assert len(pending) == 1
        assert pending[0].user_id == emp
        assert pending[0].stage == "arrival"
        assert pending[0].proposed_time == time(8, 30)
        assert pending[0].status == "pending"


def test_approve_applies_proposed_time_and_marks_corrected():
    uow, mgr, emp = _correction_scenario()
    services.submit_correction_request(uow, emp, DAY, "arrival", time(8, 30))
    request_id = _first_request_id(uow)
    services.review_correction_request(uow, mgr, request_id, True)
    with uow:
        request = uow.session.execute(select(CorrectionRequest)).scalars().first()
        assert request.status == "approved"
        user = uow.users.get_user_by_id(emp)
        ponto = next(p for p in user.time_entries if p.entry_date == DAY)
        assert ponto.arrival == time(8, 30)
        assert ponto.status.value == "Corrigido"
        assert [n.message for n in user.notifications] == [
            f"Sua solicitação de correção para {DAY} foi APROVADA."
        ]


def test_approve_recomputes_anomalies_and_clears_badge():
    uow, mgr, emp = _correction_scenario()
    services.submit_correction_request(uow, emp, DAY, "arrival", time(9, 30))
    request_id = _first_request_id(uow)
    services.review_correction_request(uow, mgr, request_id, True)
    with uow:
        user = uow.users.get_user_by_id(emp)
        ponto = next(p for p in user.time_entries if p.entry_date == DAY)
        assert ponto.arrival_late is True
        assert ponto.arrival_late_reviewed is True
        assert ponto.has_anomaly is False


def test_approve_creates_ponto_when_missing():
    uow = _session_uow()
    mgr = _register(uow, "mgr_cor2@test.com", "manager")
    emp = _register(uow, "emp_cor2@test.com", "employee")
    _team_for(uow, mgr, emp)
    _setup_schedule(uow, emp)
    services.submit_correction_request(uow, emp, DAY, "departure", time(17, 30))
    request_id = _first_request_id(uow)
    services.review_correction_request(uow, mgr, request_id, True)
    with uow:
        user = uow.users.get_user_by_id(emp)
        ponto = next(p for p in user.time_entries if p.entry_date == DAY)
        assert ponto.departure == time(17, 30)
        assert ponto.status.value == "Corrigido"


def test_reject_sets_rejected_without_touching_ponto():
    uow, mgr, emp = _correction_scenario()
    services.submit_correction_request(uow, emp, DAY, "arrival", time(8, 30))
    request_id = _first_request_id(uow)
    services.review_correction_request(uow, mgr, request_id, False)
    with uow:
        request = uow.session.execute(select(CorrectionRequest)).scalars().first()
        assert request.status == "rejected"
        user = uow.users.get_user_by_id(emp)
        ponto = next(p for p in user.time_entries if p.entry_date == DAY)
        assert ponto.arrival == time(9, 0)
        assert [n.message for n in user.notifications] == [
            f"Sua solicitação de correção para {DAY} foi REJEITADA."
        ]


def test_review_unknown_request_raises():
    uow, mgr, _ = _correction_scenario()
    with pytest.raises(ValueError):
        services.review_correction_request(uow, mgr, 9999, True)


def test_unknown_correction_stage_raises():
    uow, mgr, emp = _correction_scenario()
    with uow:
        uow.session.add(CorrectionRequest(user_id=emp, ponto_date=DAY, stage="bogus", proposed_time=time(8, 30)))
        uow.commit()
        request_id = uow.session.execute(select(CorrectionRequest)).scalars().first().request_id
    with pytest.raises(ValueError, match="desconhecido"):
        services.review_correction_request(uow, mgr, request_id, True)


def test_manager_does_not_see_outside_team_requests():
    uow = _session_uow()
    mgr = _register(uow, "mgr_cor3@test.com", "manager")
    emp = _register(uow, "emp_cor3@test.com", "employee")
    _team_for(uow, mgr, emp)
    other = _register(uow, "emp_out@test.com", "employee")
    services.submit_correction_request(uow, other, DAY, "arrival", time(8, 30))
    with uow:
        pending = services.list_pending_corrections(uow, mgr)
        assert pending == []