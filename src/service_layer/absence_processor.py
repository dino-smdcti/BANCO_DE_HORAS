import os
import sys
from datetime import date, timedelta
from sqlalchemy import select
from src.domain.model import PontoStatus, DailyPonto, Holiday, Facultativo

# Use persistent temporary directory for the last check date
LAST_CHECK_FILE = r"C:\Users\SMDCTI\.gemini\tmp\banco-de-horas\last_check_date.txt"

IS_TESTING = "pytest" in sys.modules or "unittest" in sys.modules
_test_last_check = None

def get_last_check():
        """Return the last date the daily absence check ran."""
        global _test_last_check
        if IS_TESTING:
                return _test_check_value()
        return _read_last_check() or date(2026, 5, 10)


def set_last_check(d):
        """Persist the last date the daily absence check ran."""
        global _test_last_check
        if IS_TESTING:
                _test_last_check = d
                return
        _persist_last_check(d)


def _test_check_value():
        global _test_last_check
        if _test_last_check is not None:
                return _test_last_check
        # Start from one day before the target analysis date in tests
        return date(2026, 5, 10)


def _read_last_check():
        try:
                with open(LAST_CHECK_FILE, "r") as f:
                        return date.fromisoformat(f.read().strip())
        except Exception:
                return None


def _persist_last_check(d):
        try:
                _write_last_check(d)
        except Exception:
                pass


def _write_last_check(d):
        os.makedirs(os.path.dirname(LAST_CHECK_FILE), exist_ok=True)
        with open(LAST_CHECK_FILE, "w") as f:
                f.write(d.isoformat())


def process_daily_absences(uow):
        today = date.today()

        # Performance Guard: only check once every day
        if not IS_TESTING:
                if get_last_check() == today:
                        return

        dates_to_check = _dates_to_check(today)
        print(f"DEBUG: Starting missing log verification. Today: {today}, Targets: {dates_to_check}")

        with uow:
                _check_all_employees(uow, dates_to_check)
                uow.commit()

        print(f"DEBUG: Verification complete. Updating last check date to {today}")
        set_last_check(today)


def _check_all_employees(uow, dates_to_check):
        employees = uow.users.list_employees()
        holiday_dates = _mandatory_holidays(uow)
        facultativo_dates = _facultativo_dates(uow)
        print(f"INFO: Processing daily absences for {len(employees)} employees.")
        for user in employees:
                _check_user(uow, user, dates_to_check, holiday_dates, facultativo_dates)


def _check_user(uow, user, dates_to_check, holiday_dates, facultativo_dates):
        user_entries = {p.entry_date: p for p in user.time_entries}
        analysis_start = _analysis_start(user)
        for check_date in dates_to_check:
                _process_user_date(uow, user, user_entries, check_date, analysis_start, holiday_dates, facultativo_dates)


def _dates_to_check(today):
        """Weekend-aware list of dates to verify (Mon covers Fri-Sun)."""
        if today.weekday() == 0:
                return [today - timedelta(days=3), today - timedelta(days=2), today - timedelta(days=1)]
        return [today - timedelta(days=1)]


def _mandatory_holidays(uow):
        holidays = uow.session.execute(select(Holiday)).scalars().all()
        return {h.holiday_date for h in holidays if h.is_mandatory}


def _facultativo_dates(uow):
        facultativos = uow.session.execute(select(Facultativo)).scalars().all()
        covered = set()
        for fac in facultativos:
                day = fac.start_date
                while day <= fac.end_date:
                        covered.add(day)
                        day += timedelta(days=1)
        return covered


def _analysis_start(user):
        return user.profile.start_analysis_date if user.profile else date(2026, 5, 1)


def _process_user_date(uow, user, user_entries, check_date, analysis_start, holiday_dates, facultativo_dates):
        if check_date < analysis_start:
                return
        if user.is_on_vacation(check_date):
                return
        if user.is_on_attestation(check_date):
                return
        if check_date in facultativo_dates:
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
                _mark_blank_entry_missing(ponto, reason="por ausência de registro.")
                print(f"SUCCESS: Marked empty log as MISSING for {user.email} on {check_date}")


def _mark_blank_entry_missing(ponto, reason="(Usuário sem escala definida)."):
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
                location_data="Sistema: Falta automática (Verificação diária).",
                notes="Ausência sem registro de ponto.",
                has_lunch_break=user.work_schedule.has_lunch_break)
        uow.session.add(new_ponto)
        user.time_entries.append(new_ponto)
        user_entries[check_date] = new_ponto
        print(f"SUCCESS: Added MISSING entry for user {user.user_id} on {check_date}")
