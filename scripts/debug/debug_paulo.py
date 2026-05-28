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

user = session.query(User).filter_by(user_id=7).first()
if user:
    print(f"User: {user.profile.full_name}")
    ws = user.work_schedule
    if ws:
        print(f"Schedule: Arr={ws.expected_arrival}, LunchStart={ws.expected_lunch_start}, LunchEnd={ws.expected_lunch_end}, Dep={ws.expected_departure}, Tol={ws.tolerance_minutes}")
    else:
        print("No schedule.")
    
    for p in user.time_entries[-5:]: # Look at last 5 entries
        print(f"Date: {p.entry_date}, Arr: {p.arrival}, LS: {p.lunch_start}, LE: {p.lunch_end}, Dep: {p.departure}")
        print(f"Status: {p.status}, Has Anomaly: {p.has_anomaly}")
        # Need to check why has_anomaly is true
        if p.has_anomaly:
            print("Anomaly details:")
            print(f"Arr Late: {p.arrival_late} (Approved: {p.arrival_late_approved})")
            print(f"LS Late: {p.lunch_start_late} (Approved: {p.lunch_start_late_approved})")
            print(f"LE Late: {p.lunch_end_late} (Approved: {p.lunch_end_late_approved})")
            print(f"Dep Early: {p.departure_early} (Approved: {p.departure_early_approved})")
else:
    print("User not found.")
