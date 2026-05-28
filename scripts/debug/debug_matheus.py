import os
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.domain.model import User

start_mappers()
database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()

user = session.query(User).filter_by(user_id=2).first()
if user:
    def delta(t1, t2):
        if not t1 or not t2: return 0
        from datetime import datetime, date
        d1 = datetime.combine(date.min, t1)
        d2 = datetime.combine(date.min, t2)
        return int((d2 - d1).total_seconds() / 60)

    ws = user.work_schedule
    if ws.has_lunch_break:
        target_minutes = (delta(ws.expected_arrival, ws.expected_lunch_start) + 
                          delta(ws.expected_lunch_end, ws.expected_departure))
    else:
        target_minutes = delta(ws.expected_arrival, ws.expected_departure)

    print(f"User: {user.profile.full_name or 'Unknown'}")
    print(f"Target Minutes per day: {target_minutes}")
    print(f"Total Balance: {user.total_balance / 60} hours")
else:
    print("User not found.")
