import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.domain.model import User, PontoStatus

start_mappers()
database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()

user = session.query(User).filter_by(user_id=15).first()
if user:
    print(f"User: {user.profile.full_name}")
    ws = user.work_schedule
    def delta(t1, t2):
        if not t1 or not t2: return 0
        from datetime import datetime, date
        d1 = datetime.combine(date.min, t1)
        d2 = datetime.combine(date.min, t2)
        return int((d2 - d1).total_seconds() / 60)

    if ws.has_lunch_break:
        target_minutes = (delta(ws.expected_arrival, ws.expected_lunch_start) + 
                          delta(ws.expected_lunch_end, ws.expected_departure))
    else:
        target_minutes = delta(ws.expected_arrival, ws.expected_departure)

    for p in user.time_entries:
        if p.status == PontoStatus.MISSING:
            print(f"MISSING entry found: {p.entry_date}")
            
    print(f"Target Minutes: {target_minutes}")
    for p in user.time_entries[-10:]:
        print(f"Date: {p.entry_date}, Status: {p.status}, Worked: {p.worked_minutes}, Daily Balance: {p.worked_minutes - target_minutes}")
    print(f"Total Balance: {user.total_balance / 60} hours")
else:
    print("User not found.")
