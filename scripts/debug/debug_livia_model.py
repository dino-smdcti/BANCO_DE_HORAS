import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.domain.model import DailyPonto

start_mappers()
database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()

# Check log for 2026-05-13
p = session.query(DailyPonto).filter(DailyPonto.user_id == 15, DailyPonto.entry_date == '2026-05-13').first()
if p:
    print(f"Arrival: {p.arrival}, Departure: {p.departure}")
    print(f"Has lunch break: {p.has_lunch_break}")
    # Call the model logic directly
    print(f"Worked minutes: {p.worked_minutes}")
else:
    print("Log not found.")
