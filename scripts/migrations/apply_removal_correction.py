import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
with engine.connect() as conn:
    conn.execute(text("ALTER TABLE correction_requests DROP COLUMN IF EXISTS justification;"))
    conn.commit()
    print("Column 'justification' removed from correction_requests.")
