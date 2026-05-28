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

# Check user 6 specifically
user = session.query(User).filter(User.user_id == 6).first()
if user:
    print(f"User: {user.profile.full_name}")
    print(f"Entries count: {len(user.time_entries)}")
    for p in user.time_entries:
        print(f"Entry Date: {p.entry_date}, ID: {p.ponto_id}")
else:
    print("User 6 not found.")
