import os
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.domain.model import PontoStatus, DailyPonto, Holiday

# Cutoff date requested
CUTOFF_DATE = date(2026, 5, 11)

def fill_missing_days():
    start_mappers()
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or "sqlite:///banco_de_horas.db"
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    engine = create_engine(database_url)
    uow = SqlAlchemyUnitOfWork(session_factory=sessionmaker(bind=engine))
    
    with uow:
        employees = uow.users.list_employees()
        holidays = uow.session.query(Holiday).all()
        holiday_dates = {h.holiday_date for h in holidays if h.is_mandatory}
        
        for user in employees:
            if not user.work_schedule:
                continue
                
            analysis_start = user.profile.start_analysis_date if user.profile else date(2026, 1, 1)
            
            # Ensure we don't start before the analysis date
            start_date = max(analysis_start, date(2025, 1, 1)) # Assuming a reasonable start
            
            # Iterate from analysis_start up to the cutoff date
            current_date = start_date
            while current_date <= CUTOFF_DATE:
                # 1. Workday check
                if not user.work_schedule.is_work_day(current_date):
                    current_date += timedelta(days=1)
                    continue
                
                # 2. Holiday check
                if current_date in holiday_dates:
                    current_date += timedelta(days=1)
                    continue
                
                # 3. Vacation check
                is_on_vacation = any(v.start_date <= current_date <= v.end_date for v in user.vacations)
                if is_on_vacation:
                    current_date += timedelta(days=1)
                    continue
                
                # 4. Check if entry exists
                ponto = next((p for p in user.time_entries if p.entry_date == current_date), None)
                
                if not ponto:
                    # Create MISSING entry
                    new_ponto = DailyPonto(
                        user_id=user.user_id,
                        entry_date=current_date,
                        status=PontoStatus.MISSING,
                        location_data="Sistema: Falta automática (Preenchimento em lote).",
                        notes="Ausência sem registro de ponto.",
                        has_lunch_break=user.work_schedule.has_lunch_break
                    )
                    user.time_entries.append(new_ponto)
                    print(f"Added MISSING entry for user {user.user_id} on {current_date}")
                
                current_date += timedelta(days=1)
        
        uow.commit()
        print("Missing days filled up to 11/05/2026.")

if __name__ == "__main__":
    fill_missing_days()
