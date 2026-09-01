import sys
from datetime import date, datetime, timedelta
from sqlalchemy import select
from src.domain.model import PontoStatus, DailyPonto, Holiday, Facultativo, AbsenceState
from src.config import (
        ABSENCE_DEFAULT_LAST_CHECK_DATE,
        BLANK_SCHEDULE_MISSING_REASON,
        DEFAULT_ANALYSIS_START_DATE,
        EMPTY_ENTRY_MISSING_REASON,
        MISSING_LOCATION_AUTOMATIC,
        MISSING_NOTES_AUTOMATIC,
        MONDAY_BACKLOG_DAYS,
        MONDAY_WEEKDAY_INDEX,
        PREVIOUS_DAY_OFFSET,
)

IS_TESTING = "pytest" in sys.modules or "unittest" in sys.modules
_test_last_check = None

def get_last_check(uow):
        """Return the last date the daily absence check ran, from the DB."""
        global _test_last_check
        if IS_TESTING:
                if _test_last_check is not None:
                        return _test_last_check
                return ABSENCE_DEFAULT_LAST_CHECK_DATE
        state = uow.session.execute(select(AbsenceState)).scalar_one_or_none()
        return state.last_check_date if state and state.last_check_date else ABSENCE_DEFAULT_LAST_CHECK_DATE


def set_last_check(uow, d):
        """Persist the last date the daily absence check ran to the DB (singleton row)."""
        global _test_last_check
        if IS_TESTING:
                _test_last_check = d
                return
        state = uow.session.execute(select(AbsenceState)).scalar_one_or_none()
        if state is None:
                state = AbsenceState()
                uow.session.add(state)
        state.last_check_date = d
        state.updated_at = datetime.now()


def process_daily_absences(uow):
        with uow:
                today = date.today()

                # Performance Guard: only check once every day
                if not IS_TESTING:
                        if get_last_check(uow) == today:
                                return

                dates_to_check = _dates_to_check(today)
                print(f"DEBUG: Starting missing log verification. Today: {today}, Targets: {dates_to_check}")

                _check_all_employees(uow, dates_to_check)
                set_last_check(uow, today)
                uow.commit()

        print(f"DEBUG: Verification complete. Updated last check date to {today}")


def _check_all_employees(uow, dates_to_check):
        employees = uow.users.list_employees()
        holiday_dates = _mandatory_holidays(uow)
        facultativos = _facultativos(uow)
        print(f"INFO: Processing daily absences for {len(employees)} employees.")
        for user in employees:
                _check_user(uow, user, dates_to_check, holiday_dates, facultativos)


def _check_user(uow, user, dates_to_check, holiday_dates, facultativos):
        user_entries = {p.entry_date: p for p in user.time_entries}
        analysis_start = _analysis_start(user)
        for check_date in dates_to_check:
                _process_user_date(uow, user, user_entries, check_date, analysis_start, holiday_dates, facultativos)


def _dates_to_check(today):
        """Weekend-aware list of dates to verify (Mon covers Fri-Sun)."""
        if today.weekday() == MONDAY_WEEKDAY_INDEX:
                return [today - timedelta(days=MONDAY_BACKLOG_DAYS), today - timedelta(days=2), today - timedelta(days=1)]
        return [today - timedelta(days=PREVIOUS_DAY_OFFSET)]


def _mandatory_holidays(uow):
        holidays = uow.session.execute(select(Holiday)).scalars().all()
        return {h.holiday_date for h in holidays if h.is_mandatory}


def _facultativos(uow):
        return uow.session.execute(select(Facultativo)).scalars().all()


def _is_facultativo(check_date, facultativos):
        return any(fac.start_date <= check_date <= fac.end_date for fac in facultativos)


def _analysis_start(user):
        return user.profile.start_analysis_date if user.profile else DEFAULT_ANALYSIS_START_DATE


def _process_user_date(uow, user, user_entries, check_date, analysis_start, holiday_dates, facultativos):
        if check_date < analysis_start:
                return
        if user.is_on_vacation(check_date):
                return
        if user.is_on_attestation(check_date):
                return
        if _is_facultativo(check_date, facultativos):
                return
        if not user.work_schedule:
                _mark_blank_entry_missing(user_entries.get(check_date))
                return
        if not user.work_schedule.is_work_day(check_date):
                return
        if check_date in holiday_dates:
                return
        ponto = user_entries.get(check_date)
        if not ponto:
                _add_missing_entry(uow, user, check_date, user_entries)
        elif _is_empty_entry(ponto):
                _mark_blank_entry_missing(ponto, reason=EMPTY_ENTRY_MISSING_REASON)
                print(f"SUCCESS: Marked empty log as MISSING for {user.email} on {check_date}")


def _mark_blank_entry_missing(ponto, reason=BLANK_SCHEDULE_MISSING_REASON):
        if ponto and ponto.status == PontoStatus.ON_TIME and not ponto.is_complete:
                ponto.status = PontoStatus.MISSING
                ponto.location_data = f"Sistema: Falta automática {reason}"


def _is_empty_entry(ponto):
        return (ponto.status == PontoStatus.ON_TIME
                        and not ponto.arrival and not ponto.lunch_start
                        and not ponto.lunch_end and not ponto.departure)


def _add_missing_entry(uow, user, check_date, user_entries):
        new_ponto = DailyPonto(
                user_id=user.user_id,
                entry_date=check_date,
                status=PontoStatus.MISSING,
                location_data=MISSING_LOCATION_AUTOMATIC,
                notes=MISSING_NOTES_AUTOMATIC,
                has_lunch_break=user.work_schedule.has_lunch_break)
        uow.session.add(new_ponto)
        user.time_entries.append(new_ponto)
        user_entries[check_date] = new_ponto
        print(f"SUCCESS: Added MISSING entry for user {user.user_id} on {check_date}")
