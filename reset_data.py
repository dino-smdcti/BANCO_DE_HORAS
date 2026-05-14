import os
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.domain.model import DailyPonto, User

start_mappers()
database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
uow = SqlAlchemyUnitOfWork(session_factory=sessionmaker(bind=engine))

with uow:
    cutoff_date = date(2025, 5, 11)
    
    # 1. Delete all logs before the cutoff date
    deleted = uow.session.query(DailyPonto).filter(DailyPonto.entry_date < cutoff_date).delete(synchronize_session=False)
    print(f"Deleted {deleted} logs before {cutoff_date}.")
    
    # 2. Update analysis date for all users
    # start_analysis_date is in profile, which is mapped composite in users table in ORM
    # In domain/model it's in UserProfile, but in ORM mapping it's just 'users' table columns.
    # Actually wait, the user model in domain has .profile attribute, but ORM maps 
    # columns directly to UserProfile composite object.
    # In SQL, the column is 'start_analysis_date' in 'users' table.
    uow.session.query(User).update({"start_analysis_date": cutoff_date})
    print("Updated start_analysis_date for all users.")
    
    uow.commit()
    print("Changes committed.")
