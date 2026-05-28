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

# Query everything for a known user (e.g., ID 6) to see what's really in the DB
logs = session.query(DailyPonto).filter(DailyPonto.user_id == 6).all()
print(f"Total logs for User 6: {len(logs)}")
for l in logs:
    print(f"Date: {l.entry_date}, Status: {l.status}")
