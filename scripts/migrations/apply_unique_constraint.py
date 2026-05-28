import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE daily_pontos ADD CONSTRAINT unique_user_entry_date UNIQUE (user_id, entry_date);"))
        conn.commit()
        print("Unique constraint added to daily_pontos.")
    except Exception as e:
        print(f"Error: {e}")
