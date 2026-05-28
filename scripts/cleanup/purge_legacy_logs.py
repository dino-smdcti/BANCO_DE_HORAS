import os
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.domain.model import DailyPonto

start_mappers()
database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()

cutoff_date = date(2025, 5, 11)

# Delete all logs strictly before 11/05/2025
deleted = session.query(DailyPonto).filter(DailyPonto.entry_date < cutoff_date).delete(synchronize_session=False)
session.commit()

print(f"Deleted {deleted} logs before {cutoff_date}.")
