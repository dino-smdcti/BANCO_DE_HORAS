from datetime import date, timedelta
from src.domain.model import PontoStatus, DailyPonto, Holiday

def process_daily_absences(uow):
    today = date.today()
    
    # Define which days to check based on today's weekday
    # If Monday (0), check Friday, Saturday, and Sunday
    if today.weekday() == 0:
        dates_to_check = [today - timedelta(days=3), today - timedelta(days=2), today - timedelta(days=1)]
    else:
        # Otherwise, check only yesterday
        dates_to_check = [today - timedelta(days=1)]

    with uow:
        # Get all employees
        employees = uow.users.list_employees()
        # Get all holidays
        holidays = uow.session.query(Holiday).all()
        holiday_dates = {h.holiday_date for h in holidays if h.is_mandatory}

        for user in employees:
            if not user.work_schedule:
                continue
            
            # Skip users who haven't reached their start_analysis_date yet
            analysis_start = user.profile.start_analysis_date if user.profile else None
            
            for current_date in dates_to_check:
                if analysis_start and current_date < analysis_start:
                    continue
                
                # 1. Check if it's a workday according to schedule
                if not user.work_schedule.is_work_day(current_date):
                    continue
                
                # 2. Check if it's a holiday
                if current_date in holiday_dates:
                    continue
                
                # 3. Check if user is on vacation
                is_on_vacation = any(v.start_date <= current_date <= v.end_date for v in user.vacations)
                if is_on_vacation:
                    continue
                
                # 4. Find entry
                ponto = next((p for p in user.time_entries if p.entry_date == current_date), None)
                
                if not ponto:
                    # Create MISSING entry
                    ponto = DailyPonto(
                        user_id=user.user_id,
                        entry_date=current_date,
                        status=PontoStatus.MISSING,
                        location_data="Sistema: Falta automática por ausência de registro.",
                        notes="Ausência sem registro de ponto.",
                        has_lunch_break=user.work_schedule.has_lunch_break
                    )
                    user.time_entries.append(ponto)
                    print(f"User {user.user_id} marked as MISSING for {current_date} (New entry)")
                elif ponto.status == PontoStatus.ON_TIME and \
                     not ponto.arrival and not ponto.lunch_start and \
                     not ponto.lunch_end and not ponto.departure:
                    # Mark existing empty entry as MISSING
                    ponto.status = PontoStatus.MISSING
                    ponto.location_data = "Sistema: Falta automática por ausência de registro."
                    ponto.notes = "Ausência sem registro de ponto."
                    print(f"User {user.user_id} marked as MISSING for {current_date} (Updated entry)")
        
        uow.commit()
