import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.domain.model import DailyPonto, User

start_mappers()
database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()

# Livia's ID is 15
logs = session.query(DailyPonto).filter(DailyPonto.user_id == 15).all()
for p in logs:
    print(f"Date: {p.entry_date}, Arrival: {p.arrival}, Departure: {p.departure}, Worked: {p.worked_minutes}")
