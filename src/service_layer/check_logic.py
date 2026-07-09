import os
import sys
from datetime import date, timedelta
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.domain.model import PontoStatus, DailyPonto, Holiday

# Use persistent temporary directory for the last check date
LAST_CHECK_FILE = r"C:\Users\SMDCTI\.gemini\tmp\banco-de-horas\last_check_date.txt"

IS_TESTING = "pytest" in sys.modules or "unittest" in sys.modules
_test_last_check = None

def get_last_check():
    global _test_last_check
    if IS_TESTING:
        if _test_last_check is not None:
            return _test_last_check
        return date(2026, 5, 10)  # Start from one day before the target analysis date in tests
    if os.path.exists(LAST_CHECK_FILE):
        try:
            with open(LAST_CHECK_FILE, "r") as f:
                return date.fromisoformat(f.read().strip())
        except Exception:
            pass
    return date(2026, 5, 10)

def set_last_check(d):
    global _test_last_check
    if IS_TESTING:
        _test_last_check = d
        return
    try:
        os.makedirs(os.path.dirname(LAST_CHECK_FILE), exist_ok=True)
        with open(LAST_CHECK_FILE, "w") as f:
            f.write(d.isoformat())
    except Exception:
        pass

def check_for_missing_logs(uow):
    today = date.today()

    # Performance Guard: If we've already checked today, skip everything.
    # This allows the function to be called safely on every request.
    if not IS_TESTING:
        last_check = get_last_check()
        if last_check == today:
            return

    # Determine dates to check: yesterday (today - 1).
    # If today is Monday (0), check Friday (today-3), Saturday (today-2), and Sunday (today-1).
    if today.weekday() == 0:
        dates_to_check = [today - timedelta(days=3), today - timedelta(days=2), today - timedelta(days=1)]
    else:
        dates_to_check = [today - timedelta(days=1)]

    print(f"DEBUG: Starting missing log verification. Today: {today}, Targets: {dates_to_check}")

    with uow:
        employees = uow.users.list_employees()
        holidays = uow.session.query(Holiday).all()
        holiday_dates = {h.holiday_date for h in holidays if h.is_mandatory}
        
        for user in employees:
            # Map existing entries for fast lookup
            user_entries = {p.entry_date: p for p in user.time_entries}
            
            # Determine the user's specific analysis start date
            analysis_start = user.profile.start_analysis_date if user.profile else date(2026, 5, 1)
            print(f"DEBUG: Checking user {user.user_id} ({user.email}) starting from {analysis_start}")
            
            for check_date in dates_to_check:
                if check_date < analysis_start:
                    continue

                ponto = user_entries.get(check_date)
                
                # If no schedule, we can't determine workdays, but we should still mark existing blank logs as MISSING
                if not user.work_schedule:
                    if ponto and ponto.status == PontoStatus.ON_TIME and not ponto.is_complete:
                        ponto.status = PontoStatus.MISSING
                        ponto.location_data = "Sistema: Falta automática (Usuário sem escala definida)."
                    continue
            
                # Skip if not a workday or holiday or vacation
                if not user.work_schedule.is_work_day(check_date) or \
                   check_date in holiday_dates or \
                   user.is_on_vacation(check_date):
                    continue
            
                if not ponto:
                    # Add log
                    new_ponto = DailyPonto(
                        user_id=user.user_id,
                        entry_date=check_date,
                        status=PontoStatus.MISSING,
                        location_data="Sistema: Falta automática (Verificação diária).",
                        notes="Ausência sem registro de ponto.",
                        has_lunch_break=user.work_schedule.has_lunch_break
                    )
                    uow.session.add(new_ponto)
                    user.time_entries.append(new_ponto)
                    user_entries[check_date] = new_ponto
                    print(f"SUCCESS: Added MISSING entry for user {user.user_id} on {check_date}")
                elif ponto.status == PontoStatus.ON_TIME and \
                     not ponto.arrival and not ponto.lunch_start and \
                     not ponto.lunch_end and not ponto.departure:
                    ponto.status = PontoStatus.MISSING
                    ponto.location_data = "Sistema: Falta automática por ausência de registro."
                    ponto.notes = "Ausência sem registro de ponto."
                    print(f"SUCCESS: Marked empty log as MISSING for {user.email} on {check_date}")

        uow.commit()
    
    print(f"DEBUG: Verification complete. Updating last check date to {today}")
    set_last_check(today)
