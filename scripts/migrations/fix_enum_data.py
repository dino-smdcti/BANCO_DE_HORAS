import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def fix_enum_data():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set.")
        return

    engine = create_engine(db_url)
    with engine.connect() as conn:
        print("Connected to Neon DB to fix Enum data...")
        
        commands = [
            "UPDATE work_schedules SET schedule_type = 'STANDARD' WHERE schedule_type = 'standard';",
            "UPDATE journey_types SET schedule_type = 'STANDARD' WHERE schedule_type = 'standard';"
        ]
        
        for cmd in commands:
            try:
                conn.execute(text(cmd))
                conn.commit()
                print(f"Executed: {cmd}")
            except Exception as e:
                print(f"Error executing {cmd}: {e}")

if __name__ == "__main__":
    fix_enum_data()
