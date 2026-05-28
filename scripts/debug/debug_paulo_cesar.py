import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.domain.model import User

start_mappers()
database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()

user = session.query(User).filter_by(user_id=13).first()
if user:
    print(f"User: {user.profile.full_name}")
    for p in user.time_entries:
        print(f"Date: {p.entry_date}, Status: {p.status}, Worked: {p.worked_minutes}, Excused: {p.departure_early_excused}")
    print(f"Total Balance: {user.total_balance / 60} hours")
else:
    print("User not found.")
