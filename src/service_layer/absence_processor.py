from datetime import date, timedelta
from src.domain.model import PontoStatus

def process_daily_absences(uow):
    yesterday = date.today() - timedelta(days=1)
    
    # Process only weekdays
    if yesterday.weekday() >= 5:
        return

    with uow:
        # Get all employees
        employees = uow.users.list_employees()
        for user in employees:
            ponto = next((p for p in user.time_entries if p.entry_date == yesterday), None)
            
            # If the log is "ON_TIME" (our placeholder) and completely empty, mark as MISSING
            if ponto and ponto.status == PontoStatus.ON_TIME and \
               not ponto.arrival and not ponto.lunch_start and \
               not ponto.lunch_end and not ponto.departure:
                
                ponto.status = PontoStatus.MISSING
                ponto.location_data = "Sistema: Falta automática por ausência de registro."
                ponto.notes = "Ausência sem registro de ponto."
                uow.commit()
                print(f"User {user.user_id} marked as MISSING for {yesterday}")
