

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

conn = engine.connect()

conn.execute(text("""
CREATE TABLE IF NOT EXISTS absence_state (
    id INTEGER PRIMARY KEY,
    last_check_date DATE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""))
conn.commit()
print("absence_state table created.")
conn.close()
