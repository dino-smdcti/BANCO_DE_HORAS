from datetime import date

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.service_layer import services
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.user_service import register_user


def _session_uow():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    start_mappers()
    return SqlAlchemyUnitOfWork(session_factory)


def _register(uow, email):
    with uow:
        register_user(uow, email, "pass", "employee")
        return uow.users.get_user_by_email(email).user_id


def test_full_journal_rejects_extra_clock_in():
    uow = _session_uow()
    uid = _register(uow, "dup_full@test.com")
    for _ in range(4):
        services.clock_in_out(uow, uid, "Office")
    with pytest.raises(ValueError, match="Jornada de hoje já está completa"):
        services.clock_in_out(uow, uid, "Office")


def test_stage_progression_order():
    uow = _session_uow()
    uid = _register(uow, "dup_seq@test.com")
    messages = [services.clock_in_out(uow, uid, "Office") for _ in range(4)]
    assert messages == [
        "Chegada registrada",
        "Saída para almoço registrada",
        "Retorno do almoço registrado",
        "Fim de jornada registrado",
    ]
    with uow:
        user = uow.users.get_user_by_id(uid)
        assert len(user.time_entries) == 1
        ponto = user.time_entries[0]
        assert ponto.entry_date == date.today()
        assert ponto.arrival is not None
        assert ponto.lunch_start is not None
        assert ponto.lunch_end is not None
        assert ponto.departure is not None


def test_second_clock_on_same_day_reuses_entry():
    uow = _session_uow()
    uid = _register(uow, "dup_sameday@test.com")
    services.clock_in_out(uow, uid, "Office")
    services.clock_in_out(uow, uid, "Office")
    with uow:
        user = uow.users.get_user_by_id(uid)
        assert len(user.time_entries) == 1
        assert user.time_entries[0].lunch_start is not None


def test_clock_without_schedule_defaults_lunch_break():
    uow = _session_uow()
    uid = _register(uow, "dup_nosched@test.com")
    services.clock_in_out(uow, uid, "Office")
    with uow:
        user = uow.users.get_user_by_id(uid)
        assert user.time_entries[0].has_lunch_break is True