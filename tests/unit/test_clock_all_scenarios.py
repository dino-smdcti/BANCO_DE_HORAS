"""Any clock-in/out combination must be registrable without a blocking error.

Historically the clock service raised ``"Registro de chegada não encontrado"``
when a lunch or departure stage was posted on a day that had no recorded
arrival (e.g. a late/absent arrival, or a manual advanced-stage POST). This
spec pins that every explicit stage, in any order, starts the day's log and
records itself instead of being blocked.
"""
from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.service_layer import services
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.user_service import register_user
from src.service_layer.schedule_service import set_work_schedule


def _uow():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    start_mappers()
    return SqlAlchemyUnitOfWork(sessionmaker(bind=engine, expire_on_commit=False))


def _register(uow, email, schedule=True):
    with uow:
        register_user(uow, email, "pass", "employee")
        uid = uow.users.get_user_by_email(email).user_id
        if schedule:
            set_work_schedule(
                uow, uid, uid,
                time(8, 0), time(12, 0), time(13, 0), time(17, 0),
            )
        return uid


def _ponto_for_today(uow, uid):
    with uow:
        user = uow.users.get_user_by_id(uid)
        return next((e for e in user.time_entries if e.entry_date == date.today()), None)


def _no_lunch_uow(email):
    uow = _uow()
    with uow:
        register_user(uow, email, "pass", "employee")
        uid = uow.users.get_user_by_email(email).user_id
        set_work_schedule(
            uow, uid, uid,
            time(8, 0), None, None, time(17, 0),
            has_lunch_break=False,
        )
        return uow, uid


@pytest.mark.parametrize("stage", ["arrival", "lunch_start", "lunch_end", "departure"])
def test_any_single_stage_starts_the_day(stage):
    uow = _uow()
    uid = _register(uow, f"only_{stage}@test.com")
    services.clock_in_out(uow, uid, "Office", stage=stage)
    ponto = _ponto_for_today(uow, uid)
    assert ponto is not None
    assert getattr(ponto, stage) is not None
    if stage != "arrival":
        assert ponto.arrival is None  # must not fabricate an arrival


def test_departure_first_does_not_error():
    uow = _uow()
    uid = _register(uow, "dep_first@test.com")
    services.clock_in_out(uow, uid, "Office", stage="departure")
    ponto = _ponto_for_today(uow, uid)
    assert ponto.departure is not None
    assert ponto.arrival is None


def test_partial_day_arrival_then_departure():
    uow = _uow()
    uid = _register(uow, "part@test.com")
    services.clock_in_out(uow, uid, "Office", stage="arrival")
    services.clock_in_out(uow, uid, "Office", stage="departure")
    ponto = _ponto_for_today(uow, uid)
    assert ponto.arrival is not None
    assert ponto.departure is not None
    assert ponto.lunch_start is None and ponto.lunch_end is None


def test_departure_then_arrival_out_of_order():
    uow = _uow()
    uid = _register(uow, "rev@test.com")
    services.clock_in_out(uow, uid, "Office", stage="departure")
    services.clock_in_out(uow, uid, "Office", stage="arrival")
    ponto = _ponto_for_today(uow, uid)
    assert ponto.arrival is not None
    assert ponto.departure is not None


def test_lunch_without_lunch_break_schedule_is_registerable():
    uow, uid = _no_lunch_uow("nolunch_lunch@test.com")
    services.clock_in_out(uow, uid, "Office", stage="lunch_start")
    services.clock_in_out(uow, uid, "Office", stage="lunch_end")
    ponto = _ponto_for_today(uow, uid)
    assert ponto.lunch_start is not None
    assert ponto.lunch_end is not None


def test_explicit_full_journal_overwrites_requested_stage():
    uow = _uow()
    uid = _register(uow, "full@test.com")
    for stage in ["arrival", "lunch_start", "lunch_end", "departure"]:
        services.clock_in_out(uow, uid, "Office", stage=stage)
    # Re-posting an explicit stage must not raise, just overwrite that slot.
    services.clock_in_out(uow, uid, "Office", stage="arrival")
    ponto = _ponto_for_today(uow, uid)
    assert ponto.arrival is not None