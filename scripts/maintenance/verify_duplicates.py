import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.domain.model import DailyPonto, User
from src.adapters.orm import start_mappers

# Initialize mappers
start_mappers()

database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()

entries = session.query(DailyPonto).all()
from collections import Counter
counts = Counter([e.entry_date for e in entries])
duplicates = {date: count for date, count in counts.items() if count > 1}
print(f"Duplicates: {duplicates}")
