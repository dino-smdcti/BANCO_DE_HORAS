import os
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.domain.model import DailyPonto

start_mappers()
engine = create_engine(os.environ.get("DATABASE_URL"))
Session = sessionmaker(bind=engine)
session = Session()

cutoff_date = date(2025, 5, 11)
logs = session.query(DailyPonto).filter(DailyPonto.entry_date < cutoff_date).all()
print(f"Found {len(logs)} logs before {cutoff_date}:")
for l in logs:
    print(f"ID: {l.ponto_id}, Date: {l.entry_date}, Marker: {l.location_data}")
