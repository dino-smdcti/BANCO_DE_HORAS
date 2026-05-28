import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def migrate_manager_notes():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set.")
        return

    engine = create_engine(db_url)
    with engine.connect() as conn:
        print("Connected to DB to add manager_notes...")
        try:
            conn.execute(text("ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS manager_notes TEXT;"))
            conn.commit()
            print("Successfully added manager_notes column.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    migrate_manager_notes()
