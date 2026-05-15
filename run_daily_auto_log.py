import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.auto_log import generate_automatic_logs
from src.domain.model import User

def run_batch_auto_log():
    start_mappers()
    database_url = os.environ.get("DATABASE_URL")
    engine = create_engine(database_url)
    uow = SqlAlchemyUnitOfWork(session_factory=sessionmaker(bind=engine))
    
    with uow:
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
