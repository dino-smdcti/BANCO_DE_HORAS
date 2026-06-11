import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.auto_log import generate_automatic_logs
from src.service_layer.absence_processor import process_daily_absences

def run_batch_auto_log():
    load_dotenv()
    start_mappers()
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or "sqlite:///banco_de_horas.db"
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    engine = create_engine(database_url)
    uow = SqlAlchemyUnitOfWork(session_factory=sessionmaker(bind=engine))
    
    with uow:
        # 1. Process Absences (Marks missing days as Faltante)
        print("Running absence processor...")
        try:
            process_daily_absences(uow)
        except Exception as e:
            print(f"Error processing absences: {e}")

        # 2. Generate Automatic Logs (Currently disabled in auto_log.py)
        employees = uow.users.list_employees()
        print(f"Running auto-log for {len(employees)} employees...")
        for user in employees:
            try:
                generate_automatic_logs(uow, user)
            except Exception as e:
                print(f"Error processing user {user.user_id}: {e}")
                
    print("Batch processing completed.")

if __name__ == "__main__":
    run_batch_auto_log()
