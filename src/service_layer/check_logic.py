import os
from datetime import date, timedelta
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.domain.model import PontoStatus, DailyPonto, Holiday

# Use persistent temporary directory for the last check date
LAST_CHECK_FILE = r"C:\Users\SMDCTI\.gemini\tmp\banco-de-horas\last_check_date.txt"

def get_last_check():
    if os.path.exists(LAST_CHECK_FILE):
        with open(LAST_CHECK_FILE, "r") as f:
            return date.fromisoformat(f.read().strip())
    return date(2026, 1, 1)

def set_last_check(d):
    with open(LAST_CHECK_FILE, "w") as f:
        f.write(d.isoformat())

def check_for_missing_logs(uow):
    today = date.today()
    last_check = get_last_check()
    
    if last_check >= today:
        return
        
    yesterday = today - timedelta(days=1)
    
    # Only check up to yesterday
    check_date = yesterday
    
    with uow:
        employees = uow.users.list_employees()
        holidays = uow.session.query(Holiday).all()
        holiday_dates = {h.holiday_date for h in holidays if h.is_mandatory}
        
        for user in employees:
            if not user.work_schedule:
                continue
            
            # Skip if not a workday or holiday or vacation
            if not user.work_schedule.is_work_day(check_date) or \
               check_date in holiday_dates or \
               any(v.start_date <= check_date <= v.end_date for v in user.vacations):
                continue
            
            # Check for existing log
            ponto = next((p for p in user.time_entries if p.entry_date == check_date), None)
            
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
                user.time_entries.append(new_ponto)
                print(f"Added MISSING entry for user {user.user_id} on {check_date}")
        
        uow.commit()
    
    set_last_check(today)
    print(f"Check for {check_date} completed.")
