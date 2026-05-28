import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork

start_mappers()
engine = create_engine(os.environ.get("DATABASE_URL"))
uow = SqlAlchemyUnitOfWork(session_factory=sessionmaker(bind=engine))

with uow:
    user = uow.users.get_user_by_id(6)
    if user:
        print(f"Work Schedule: {user.work_schedule}")
    else:
        print("User not found.")
