import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.domain.model import DailyPonto

start_mappers()
database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()

# Find all entries and keep only the first one for each (user_id, entry_date)
entries = session.query(DailyPonto).all()
seen = set()
to_delete = []

for e in entries:
    key = (e.user_id, e.entry_date)
    if key in seen:
        to_delete.append(e)
    else:
        seen.add(key)

print(f"Deleting {len(to_delete)} duplicate logs to enable unique constraint...")
for e in to_delete:
    session.delete(e)

session.commit()
print("Cleanup complete. Retrying unique constraint...")
session.execute(text("ALTER TABLE daily_pontos ADD CONSTRAINT unique_user_entry_date UNIQUE (user_id, entry_date);"))
session.commit()
print("Unique constraint added.")
