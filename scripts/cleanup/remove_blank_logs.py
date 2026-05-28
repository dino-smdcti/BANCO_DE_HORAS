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

# Define what constitutes a "blank" log:
# Logs that are NOT complete (missing arrival/departure) and have no specific status or notes
# Or logs that are specifically MISSING status and were auto-generated.
# The user wants to remove "logs em branco".
# Let's target logs where arrival, lunch_start, lunch_end, and departure are all NULL.
deleted = session.query(DailyPonto).filter(
    DailyPonto.arrival == None,
    DailyPonto.lunch_start == None,
    DailyPonto.lunch_end == None,
    DailyPonto.departure == None
).delete(synchronize_session=False)

session.commit()
print(f"Deleted {deleted} blank logs.")
