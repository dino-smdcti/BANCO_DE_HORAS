from datetime import date, timedelta, time
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
import src.service_layer.absence_processor as ap
from src.domain.model import DailyPonto, Holiday, PontoStatus, UserProfile, Vacation
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
        uid = uow.users.get_user_by_email(email).user_id
        uow.users.get_user_by_id(uid).profile = UserProfile(start_analysis_date=date(2026, 5, 1))
        uow.commit()
        return uid


def _schedule(uow, uid):
    services.set_work_schedule(uow, uid, uid, time(8, 0), time(12, 0), time(13, 0), time(17, 0))


def _run_processor(uow, target_date):
    with patch.object(ap, "IS_TESTING", False), patch.object(ap, "_test_last_check", None):
        with patch("src.service_layer.absence_processor.date") as mock_date:
            mock_date.today.return_value = target_date
            mock_date.fromisoformat = date.fromisoformat
            with patch("src.service_layer.absence_processor.get_last_check", return_value=target_date - timedelta(days=1)):
                ap.process_daily_absences(uow)


def _entries_by_date(uow, uid):
    with uow:
        user = uow.users.get_user_by_id(uid)
        return {p.entry_date: p for p in user.time_entries}


def test_adds_missing_entry_for_yesterday():
    uow = _session_uow()
    uid = _register(uow, "abs@test.com")
    _schedule(uow, uid)
    _run_processor(uow, date(2026, 5, 12))
    with uow:
        entries = _entries_by_date(uow, uid)
        assert date(2026, 5, 11) in entries
        assert entries[date(2026, 5, 11)].status is PontoStatus.MISSING


def test_marks_blank_entry_as_missing():
    uow = _session_uow()
    uid = _register(uow, "abs_blank@test.com")
    _schedule(uow, uid)
    with uow:
        user = uow.users.get_user_by_id(uid)
        user.time_entries.append(DailyPonto(user_id=uid, entry_date=date(2026, 5, 11), has_lunch_break=True, status=PontoStatus.ON_TIME))
        uow.commit()
    _run_processor(uow, date(2026, 5, 12))
    with uow:
        entries = _entries_by_date(uow, uid)
        assert entries[date(2026, 5, 11)].status is PontoStatus.MISSING


def test_monday_backlog_skips_weekends_and_holiday():
    uow = _session_uow()
    uid = _register(uow, "abs_backlog@test.com")
    _schedule(uow, uid)
    with uow:
        uow.session.add(Holiday(holiday_date=date(2026, 5, 8), description="Teste", is_mandatory=True))
        uow.commit()
    # Monday: backlog covers Fri 8, Sat 9, Sun 10 (Fri is a holiday, weekend is not a work day).
    _run_processor(uow, date(2026, 5, 11))
    with uow:
        entries = _entries_by_date(uow, uid)
        assert set(entries) == set()


def test_skips_vacation_day():
    uow = _session_uow()
    uid = _register(uow, "abs_vac@test.com")
    _schedule(uow, uid)
    with uow:
        user = uow.users.get_user_by_id(uid)
        user.vacations.append(Vacation(user_id=uid, start_date=date(2026, 5, 11), end_date=date(2026, 5, 11)))
        uow.commit()
    _run_processor(uow, date(2026, 5, 12))
    with uow:
        entries = _entries_by_date(uow, uid)
        assert date(2026, 5, 11) not in entries


def test_user_without_schedule_gets_no_entry():
    uow = _session_uow()
    uid = _register(uow, "abs_noschedule@test.com")
    _run_processor(uow, date(2026, 5, 12))
    with uow:
        entries = _entries_by_date(uow, uid)
        assert date(2026, 5, 11) not in entries


def test_completed_entry_is_untouched():
    uow = _session_uow()
    uid = _register(uow, "abs_complete@test.com")
    _schedule(uow, uid)
    with uow:
        user = uow.users.get_user_by_id(uid)
        user.time_entries.append(DailyPonto(
            user_id=uid, entry_date=date(2026, 5, 11), arrival=time(8, 0), lunch_start=time(12, 0),
            lunch_end=time(13, 0), departure=time(17, 0), has_lunch_break=True, status=PontoStatus.ON_TIME))
        uow.commit()
    _run_processor(uow, date(2026, 5, 12))
    with uow:
        entries = _entries_by_date(uow, uid)
        ponto = entries[date(2026, 5, 11)]
        assert ponto.status is PontoStatus.ON_TIME
        assert ponto.is_complete is True