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

# Check ALL users to see if any have logs
users = session.query(User).all()
for u in users:
    if len(u.time_entries) > 0:
        print(f"User {u.profile.full_name} has {len(u.time_entries)} logs.")
