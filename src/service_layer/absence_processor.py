from datetime import date, timedelta
from src.domain.model import PontoStatus, DailyPonto, Holiday
from src.service_layer.check_logic import get_last_check, set_last_check, IS_TESTING

def process_daily_absences(uow):
    today = date.today()
    
    # Performance Guard: only check once every day
    if not IS_TESTING:
        last_check = get_last_check()
        if last_check == today:
            return

    # Define which days to check based on today's weekday
    # If Monday (0), check Friday, Saturday, and Sunday
    if today.weekday() == 0:
        dates_to_check = [today - timedelta(days=3), today - timedelta(days=2), today - timedelta(days=1)]
    else:
        # Otherwise, check only yesterday
        dates_to_check = [today - timedelta(days=1)]

    print(f"DEBUG: Starting missing log verification. Today: {today}, Targets: {dates_to_check}")

    with uow:
        # Get all employees
        employees = uow.users.list_employees()
        print(f"INFO: Processing daily absences for {len(employees)} employees.")
        # Get all holidays
        holidays = uow.session.query(Holiday).all()
        holiday_dates = {h.holiday_date for h in holidays if h.is_mandatory}

        for user in employees:
            # Map existing entries for fast lookup
            user_entries = {p.entry_date: p for p in user.time_entries}
            
            # Skip users who haven't reached their start_analysis_date yet
            analysis_start = user.profile.start_analysis_date if user.profile else date(2026, 5, 1)
            
            for check_date in dates_to_check:
                if check_date < analysis_start:
                    continue
                
                # If no schedule, we can't determine workdays, but we should still mark existing blank logs as MISSING
                if not user.work_schedule:
                    ponto = user_entries.get(check_date)
                    if ponto and ponto.status == PontoStatus.ON_TIME and not ponto.is_complete:
                        ponto.status = PontoStatus.MISSING
                        ponto.location_data = "Sistema: Falta automática (Usuário sem escala definida)."
                    continue
                
                # 1. Check if it's a workday according to schedule
                if not user.work_schedule.is_work_day(check_date):
                    continue
                
                # 2. Check if it's a holiday
                if check_date in holiday_dates:
                    continue
                
                # 3. Check if user is on vacation
                is_on_vacation = any(v.start_date <= check_date <= v.end_date for v in user.vacations)
                if is_on_vacation:
                    continue
                
                # 4. Find entry
                ponto = user_entries.get(check_date)
                
                if not ponto:
                    # Create MISSING entry
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
                    # Mark existing empty entry as MISSING
                    ponto.status = PontoStatus.MISSING
                    ponto.location_data = "Sistema: Falta automática por ausência de registro."
                    ponto.notes = "Ausência sem registro de ponto."
                    print(f"SUCCESS: Marked empty log as MISSING for {user.email} on {check_date}")
        
        uow.commit()

    print(f"DEBUG: Verification complete. Updating last check date to {today}")
    set_last_check(today)
