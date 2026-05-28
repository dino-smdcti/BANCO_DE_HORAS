import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def apply_migrations():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set.")
        return

    engine = create_engine(db_url)
    with engine.connect() as conn:
        print("Connected to Neon DB...")
        
        commands = [
            "ALTER TABLE work_schedules ADD COLUMN IF NOT EXISTS schedule_type TEXT DEFAULT 'standard';",
            "ALTER TABLE work_schedules ADD COLUMN IF NOT EXISTS rotation_start_date DATE;",
            "ALTER TABLE journey_types ADD COLUMN IF NOT EXISTS schedule_type TEXT DEFAULT 'standard';"
        ]
        
        for cmd in commands:
            try:
                conn.execute(text(cmd))
                conn.commit()
                print(f"Executed: {cmd}")
            except Exception as e:
                print(f"Error executing {cmd}: {e}")

if __name__ == "__main__":
    apply_migrations()
