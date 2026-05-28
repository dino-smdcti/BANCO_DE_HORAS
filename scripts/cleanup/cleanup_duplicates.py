import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.domain.model import DailyPonto
from src.adapters.orm import start_mappers

start_mappers()

database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()

# Group by user_id and entry_date to find true duplicates per user
entries = session.query(DailyPonto).all()
seen = set()
to_delete = []

for e in entries:
    key = (e.user_id, e.entry_date)
    if key in seen:
        to_delete.append(e)
    else:
        seen.add(key)

print(f"Deleting {len(to_delete)} duplicate logs...")
for e in to_delete:
    session.delete(e)

session.commit()
print("Done.")
