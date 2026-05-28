import os
from datetime import date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.domain.model import User

start_mappers()
database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()

# Set start_analysis_date to 2026-05-11 for all users
new_date = date(2026, 5, 11)
session.query(User).update({"start_analysis_date": new_date})
session.commit()
print(f"Updated all users' start_analysis_date to {new_date}.")
