import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def migrate_data():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set.")
        return

    engine = create_engine(db_url)
    with engine.connect() as conn:
        print("Connected to Neon DB...")
        
        # Update existing data
        conn.execute(text("UPDATE work_schedules SET schedule_type = 'STANDARD' WHERE schedule_type = 'standard'"))
        conn.execute(text("UPDATE journey_types SET schedule_type = 'STANDARD' WHERE schedule_type = 'standard'"))
        conn.commit()
        
        print("Data migration completed (standard -> STANDARD).")

if __name__ == "__main__":
    migrate_data()
