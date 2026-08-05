import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
with engine.connect() as conn:
    conn.execute(text("ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS excused_minutes INTEGER DEFAULT 0;"))
    conn.commit()
    print("Column 'excused_minutes' added to daily_pontos.")
