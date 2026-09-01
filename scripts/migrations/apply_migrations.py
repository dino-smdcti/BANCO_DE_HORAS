import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from src.service_layer.unit_of_work import resolve_database_url

BASE_MIGRATIONS = [
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
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS departure_early_approved BOOLEAN DEFAULT FALSE;",

    # Support individual anomaly excuse
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS arrival_late_excused BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS lunch_start_late_excused BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS lunch_end_late_excused BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS departure_early_excused BOOLEAN DEFAULT FALSE;",

    # Support individual anomaly review status
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS arrival_late_reviewed BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS lunch_start_late_reviewed BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS lunch_end_late_reviewed BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS departure_early_reviewed BOOLEAN DEFAULT FALSE;",

    # Support early lunch start anomaly (independent from late lunch start)
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS lunch_start_early BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS lunch_start_early_approved BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS lunch_start_early_excused BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS lunch_start_early_reviewed BOOLEAN DEFAULT FALSE;",

    # Replace "!" password sentinel with an explicit password_set flag
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_set BOOLEAN NOT NULL DEFAULT FALSE;",
    "UPDATE users SET password_set = TRUE WHERE password_hash <> '_unset_password_' AND password_hash <> '!';",
    "UPDATE users SET password_hash = '_unset_password_' WHERE password_hash = '!';",

    # Team ownership model (manager scoping / IDOR hardening). The teams table is
    # created by metadata.create_all on fresh databases; this covers existing ones.
    "CREATE TABLE IF NOT EXISTS teams (id SERIAL PRIMARY KEY, name VARCHAR(100) UNIQUE NOT NULL, secretariat VARCHAR(100));",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(id);",
    # Backfill a default team so existing users remain scoped together until
    # administrators reorganise teams through the Teams admin page.
    "INSERT INTO teams (name) SELECT 'Geral' WHERE NOT EXISTS (SELECT 1 FROM teams);",
    "UPDATE users SET team_id = (SELECT id FROM teams WHERE name = 'Geral') WHERE team_id IS NULL;",
]


def run_base_migrations(engine):
    with engine.connect() as conn:
        for sql in BASE_MIGRATIONS:
            try:
                print(f"Executing: {sql}")
                conn.execute(text(sql))
                conn.commit()
                print("Success.")
            except Exception as e:
                print(f"Error executing migration: {e}")
                conn.rollback()


def main():
    load_dotenv()
    print(f"Connecting to database...")
    engine = create_engine(resolve_database_url())
    run_base_migrations(engine)
    print("Migrations completed.")


if __name__ == "__main__":
    main()