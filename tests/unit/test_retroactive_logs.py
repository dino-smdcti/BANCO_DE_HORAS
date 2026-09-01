from datetime import date, timedelta, time

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.domain.model import Attestation, DailyPonto, Facultativo, Holiday, PontoStatus, Team, UserProfile, Vacation
from src.service_layer import services
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.user_service import register_user

START = date(2026, 5, 4)
END = date(2026, 5, 11)


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
        team = Team(name="equipe_retro")
        uow.session.add(team)
        uow.commit()
        uow.users.get_user_by_id(mgr).team_id = team.team_id
        uow.users.get_user_by_id(emp).team_id = team.team_id
        uow.commit()


def _scenario():
    uow = _session_uow()
    mgr = _register(uow, "mgr_retro@test.com", "manager")
    emp = _register(uow, "emp_retro@test.com", "employee")
    _team_for(uow, mgr, emp)
    services.set_work_schedule(uow, emp, emp, time(8, 0), time(12, 0), time(13, 0), time(17, 0))
    with uow:
        user = uow.users.get_user_by_id(emp)
        user.profile = UserProfile(start_analysis_date=START)
        uow.commit()
    return uow, mgr, emp


def _entry_dates(uow, emp):
    with uow:
        user = uow.users.get_user_by_id(emp)
        return sorted(p.entry_date for p in user.time_entries)


def _entry(uow, emp, day):
    with uow:
        user = uow.users.get_user_by_id(emp)
        for p in user.time_entries:
            if p.entry_date == day:
                return p
        return None


def test_creates_entries_for_workdays_only():
    uow, mgr, emp = _scenario()
    created, updated, skipped = services.complete_retroactive_logs(uow, mgr, emp, END, fill_with_schedule=True)
    assert created == 6
    assert updated == 0
    assert skipped == 2
    assert _entry_dates(uow, emp) == [date(2026, 5, 4), date(2026, 5, 5), date(2026, 5, 6), date(2026, 5, 7), date(2026, 5, 8), date(2026, 5, 11)]
    entry = _entry(uow, emp, date(2026, 5, 4))
    assert entry.arrival == time(8, 0)
    assert entry.departure == time(17, 0)
    assert entry.status is PontoStatus.ON_TIME


def test_skips_vacation_attestation_holiday_and_facultativo():
    uow, mgr, emp = _scenario()
    with uow:
        user = uow.users.get_user_by_id(emp)
        user.vacations.append(Vacation(user_id=emp, start_date=date(2026, 5, 5), end_date=date(2026, 5, 6)))
        user.attestations.append(Attestation(user_id=emp, start_date=date(2026, 5, 7), end_date=date(2026, 5, 7)))
        uow.session.add(Holiday(holiday_date=date(2026, 5, 8), description="Ponto teste", is_mandatory=True))
        uow.session.add(Facultativo(start_date=date(2026, 5, 11), end_date=date(2026, 5, 11), description="Facultativo teste"))
        uow.commit()
    created, updated, skipped = services.complete_retroactive_logs(uow, mgr, emp, END, fill_with_schedule=True)
    assert created == 1
    assert skipped == 7
    assert _entry_dates(uow, emp) == [date(2026, 5, 4)]


def test_fills_blank_existing_only_when_flagged():
    uow, mgr, emp = _scenario()
    with uow:
        user = uow.users.get_user_by_id(emp)
        user.time_entries.append(DailyPonto(user_id=emp, entry_date=date(2026, 5, 4), has_lunch_break=True, status=PontoStatus.ON_TIME))
        uow.commit()
    created, updated, _ = services.complete_retroactive_logs(uow, mgr, emp, END, fill_with_schedule=True, fill_blank_existing=False)
    assert created == 5
    assert updated == 0
    blank = _entry(uow, emp, date(2026, 5, 4))
    assert blank.arrival is None

    created, updated, _ = services.complete_retroactive_logs(uow, mgr, emp, END, fill_with_schedule=True, fill_blank_existing=True)
    assert created == 0
    assert updated == 1
    filled = _entry(uow, emp, date(2026, 5, 4))
    assert filled.arrival == time(8, 0)
    assert filled.status is PontoStatus.ON_TIME


def test_overwrite_existing_requires_flag():
    uow, mgr, emp = _scenario()
    with uow:
        user = uow.users.get_user_by_id(emp)
        user.time_entries.append(DailyPonto(
            user_id=emp, entry_date=date(2026, 5, 4), arrival=time(9, 0), departure=time(18, 0),
            has_lunch_break=True, status=PontoStatus.ON_TIME))
        uow.commit()
    created, updated, _ = services.complete_retroactive_logs(uow, mgr, emp, END, fill_with_schedule=True, overwrite_existing=False)
    assert created == 5
    assert updated == 0
    assert _entry(uow, emp, date(2026, 5, 4)).arrival == time(9, 0)

    created, updated, _ = services.complete_retroactive_logs(uow, mgr, emp, END, fill_with_schedule=True, overwrite_existing=True)
    assert created == 0
    assert updated == 6
    assert _entry(uow, emp, date(2026, 5, 4)).arrival == time(8, 0)


def test_manual_times_produce_corrected_entries():
    uow, mgr, emp = _scenario()
    created, updated, _ = services.complete_retroactive_logs(
        uow, mgr, emp, date(2026, 5, 5), fill_with_schedule=False,
        manual_arrival=time(7, 30), manual_departure=time(16, 30),
    )
    assert created == 2
    entry = _entry(uow, emp, date(2026, 5, 4))
    assert entry.arrival == time(7, 30)
    assert entry.departure == time(16, 30)
    assert entry.status is PontoStatus.CORRECTED


def test_rejects_end_before_start():
    uow, mgr, emp = _scenario()
    with pytest.raises(ValueError):
        services.complete_retroactive_logs(uow, mgr, emp, START - timedelta(days=1), fill_with_schedule=True)


def test_cross_team_manager_denied():
    uow = _session_uow()
    mgr = _register(uow, "mgr_retro2@test.com", "manager")
    emp = _register(uow, "emp_retro2@test.com", "employee")
    with uow:
        team_a = Team(name="a")
        team_b = Team(name="b")
        uow.session.add_all([team_a, team_b])
        uow.commit()
        uow.users.get_user_by_id(mgr).team_id = team_a.team_id
        uow.users.get_user_by_id(emp).team_id = team_b.team_id
        uow.commit()
        uow.users.get_user_by_id(emp).profile = UserProfile(start_analysis_date=START)
        uow.commit()
    with pytest.raises(PermissionError):
        services.complete_retroactive_logs(uow, mgr, emp, END, fill_with_schedule=True)