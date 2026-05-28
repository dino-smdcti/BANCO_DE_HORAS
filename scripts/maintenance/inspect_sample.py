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

# Check sample entry
e = session.query(DailyPonto).first()
if e:
    print(f"Sample Entry: UserID={e.user_id}, Date={e.entry_date}, Status={e.status}")
else:
    print("No entries.")
