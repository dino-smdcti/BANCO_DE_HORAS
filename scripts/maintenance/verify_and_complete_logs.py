import os
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.domain.model import PontoStatus, DailyPonto, Holiday

# Target date
TARGET_DATE = date(2026, 5, 11)

def verify_and_complete_logs():
    start_mappers()
    # Assuming standard database connection logic
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
            
            # Identify workdays from analysis start up to TARGET_DATE
            analysis_start = user.profile.start_analysis_date if user.profile else date(2026, 1, 1)
            start_date = max(analysis_start, date(2025, 1, 1))
            
            # Map existing entries for fast lookup
            existing_entries = {p.entry_date for p in user.time_entries}
            
            current_date = start_date
            while current_date <= TARGET_DATE:
                # Skip non-workdays, holidays, vacations
                if not user.work_schedule.is_work_day(current_date) or \
                   current_date in holiday_dates or \
                   user.is_on_vacation(current_date):
                    continue
                
                # Check for missing log
                if current_date not in existing_entries:
                    new_ponto = DailyPonto(
                        user_id=user.user_id,
                        entry_date=current_date,
                        status=PontoStatus.MISSING,
                        location_data="Sistema: Falta automática (Verificação de completude).",
                        notes="Ausência sem registro de ponto.",
                        has_lunch_break=user.work_schedule.has_lunch_break
                    )
                    user.time_entries.append(new_ponto)
                    print(f"Added MISSING entry for user {user.user_id} on {current_date}")
                    existing_entries.add(current_date)
                
                current_date += timedelta(days=1)
        
        uow.commit()
        print("Verification and completion check finished.")

if __name__ == "__main__":
    verify_and_complete_logs()
