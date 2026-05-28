from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
import os

start_mappers()
engine = create_engine(os.environ.get("DATABASE_URL"))
uow = SqlAlchemyUnitOfWork(session_factory=sessionmaker(bind=engine))

with uow:
    users = uow.users.list_all()
    for u in users:
        print(f"ID: {u.user_id}, Name: {u.profile.full_name}, Email: {u.email}")
