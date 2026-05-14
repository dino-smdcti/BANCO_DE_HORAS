
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

database_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

if not database_url:
    print("DATABASE_URL not found. Please set it in your environment or .env file.")
    exit(1)

engine = create_engine(database_url)

migrations = [
    # Support optional lunch breaks in work_schedules
    "ALTER TABLE work_schedules ADD COLUMN IF NOT EXISTS has_lunch_break BOOLEAN DEFAULT TRUE;",
    "ALTER TABLE work_schedules ALTER COLUMN expected_lunch_start DROP NOT NULL;",
    "ALTER TABLE work_schedules ALTER COLUMN expected_lunch_end DROP NOT NULL;",

    # Support optional lunch breaks in journey_types
    "ALTER TABLE journey_types ADD COLUMN IF NOT EXISTS has_lunch_break BOOLEAN DEFAULT TRUE;",
    "ALTER TABLE journey_types ALTER COLUMN expected_lunch_start DROP NOT NULL;",
    "ALTER TABLE journey_types ALTER COLUMN expected_lunch_end DROP NOT NULL;",

    # Support optional lunch breaks in daily_pontos
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS has_lunch_break BOOLEAN DEFAULT TRUE;",

    # Support individual anomaly approval
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS arrival_late_approved BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS lunch_start_late_approved BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS lunch_end_late_approved BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS departure_early_approved BOOLEAN DEFAULT FALSE;"
]

print(f"Connecting to database...")
with engine.connect() as conn:
    for sql in migrations:
        try:
            print(f"Executing: {sql}")
            conn.execute(text(sql))
            conn.commit()
            print("Success.")
        except Exception as e:
            print(f"Error executing migration: {e}")
            conn.rollback()

print("Migrations completed.")
