import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.domain.model import PontoStatus, DailyPonto

def fill_missing_entries():
    start_mappers()
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or "sqlite:///banco_de_horas.db"
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    engine = create_engine(database_url)
    uow = SqlAlchemyUnitOfWork(session_factory=sessionmaker(bind=engine))
    
    with uow:
        # Query all MISSING ponto entries
        missing_pontos = uow.session.query(DailyPonto).filter(DailyPonto.status == PontoStatus.MISSING).all()
        
        count = 0
        for ponto in missing_pontos:
            user = uow.users.get_user_by_id(ponto.user_id)
            if not user or not user.work_schedule:
                continue
            
            # Skip excluded users
            if user.full_name in ('Ana Clara', 'Matheus'):
                continue
            
            # Fill times from schedule
            ponto.arrival = user.work_schedule.expected_arrival
            ponto.lunch_start = user.work_schedule.expected_lunch_start
            ponto.lunch_end = user.work_schedule.expected_lunch_end
            ponto.departure = user.work_schedule.expected_departure
            
            # Update status
            ponto.status = PontoStatus.ON_TIME
            ponto.notes = "Preenchimento automático conforme jornada."
            ponto.location_data = "Sistema: Preenchimento automático."
            
            count += 1
            if count % 100 == 0:
                print(f"Filled {count} entries...")
        
        uow.commit()
        print(f"Successfully filled {count} missing entries.")

if __name__ == "__main__":
    fill_missing_entries()
