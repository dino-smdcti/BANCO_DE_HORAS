import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.domain.model import AuditLog

def purge_clock_event_logs():
    start_mappers()
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or "sqlite:///banco_de_horas.db"
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    engine = create_engine(database_url)
    uow = SqlAlchemyUnitOfWork(session_factory=sessionmaker(bind=engine))
    
    with uow:
        # Delete entries where action is CLOCK_EVENT
        logs_to_delete = uow.session.query(AuditLog).filter(AuditLog.action == 'CLOCK_EVENT').all()
        count = len(logs_to_delete)
        for log in logs_to_delete:
            uow.session.delete(log)
        
        uow.commit()
        print(f"Purged {count} CLOCK_EVENT logs.")

if __name__ == "__main__":
    purge_clock_event_logs()
