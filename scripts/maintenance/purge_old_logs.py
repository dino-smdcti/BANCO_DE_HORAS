import os
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.domain.model import DailyPonto

# Cutoff date
CUTOFF_DATE = date(2026, 5, 11)

def purge_old_logs():
    start_mappers()
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or "sqlite:///banco_de_horas.db"
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    engine = create_engine(database_url)
    uow = SqlAlchemyUnitOfWork(session_factory=sessionmaker(bind=engine))
    
    with uow:
        # Delete entries before CUTOFF_DATE
        old_entries = uow.session.query(DailyPonto).filter(DailyPonto.entry_date < CUTOFF_DATE).all()
        count = len(old_entries)
        for entry in old_entries:
            uow.session.delete(entry)
        
        uow.commit()
        print(f"Purged {count} logs before {CUTOFF_DATE}.")

if __name__ == "__main__":
    purge_old_logs()
