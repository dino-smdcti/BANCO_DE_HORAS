import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import os
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load environment variable for database URL, fallback to .env file
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    # Attempt to read .env file in project root
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    if os.path.isfile(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith('DATABASE_URL'):
                    _, val = line.strip().split('=', 1)
                    DATABASE_URL = val
                    break
    if not DATABASE_URL:
        raise RuntimeError('DATABASE_URL not set in environment and .env file not found')

# Import ORM mappings and models
from src.adapters.orm import start_mappers, metadata
from src.domain.model import User, DailyPonto

# Initialize ORM mappings
start_mappers()

# Set up database engine and session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# Repository for convenience (optional)
from src.adapters.repository import SqlAlchemyRepository
repo = SqlAlchemyRepository(session)

def get_user_by_name(name_fragment: str):
    """Case‑insensitive search for user by name fragment."""
    return session.query(User).filter(User.full_name.ilike(f'%{name_fragment}%')).first()

def fill_missing_entries(user_name: str, up_to: date):
    user = get_user_by_name(user_name)
    if not user:
        print(f'User "{user_name}" not found')
        return
    schedule = user.work_schedule
    if not schedule:
        print('User has no work schedule defined')
        return
    start_date = user.profile.start_analysis_date if user.profile and user.profile.start_analysis_date else date.today()
    current = start_date
    added = 0
    while current <= up_to:
        if schedule.is_work_day(current):
            exists = session.query(DailyPonto).filter_by(user_id=user.user_id, entry_date=current).first()
            if not exists:
                entry = DailyPonto(
                    user_id=user.user_id,
                    entry_date=current,
                    arrival=schedule.expected_arrival,
                    lunch_start=schedule.expected_lunch_start,
                    lunch_end=schedule.expected_lunch_end,
                    departure=schedule.expected_departure,
                )
                session.add(entry)
                added += 1
        current += timedelta(days=1)
    session.commit()
    print(f'Added {added} missing clock‑in/out entries for {user.full_name}')

if __name__ == '__main__':
    target_date = date(2026, 5, 1)
    fill_missing_entries('Nágela', target_date)
