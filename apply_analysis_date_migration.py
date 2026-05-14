import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
with engine.connect() as conn:
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS start_analysis_date DATE DEFAULT '2026-01-01';"))
    conn.commit()
    print("Column 'start_analysis_date' added to users.")
