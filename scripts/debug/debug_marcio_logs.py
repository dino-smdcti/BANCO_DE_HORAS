import os
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.auto_log import generate_automatic_logs

start_mappers()
database_url = os.environ.get("DATABASE_URL")
engine = create_engine(database_url)
uow = SqlAlchemyUnitOfWork(session_factory=sessionmaker(bind=engine))

with uow:
    user = uow.users.get_user_by_id(6) # Marcio
    if user:
        print(f"User: {user.profile.full_name}")
        print(f"Start Analysis Date: {user.profile.start_analysis_date}")
        
        # Remove the marker to force run
        auto_log_marker = "Sistema: Gerador Automático Executado"
        markers = [p for p in user.time_entries if auto_log_marker in (p.location_data or "")]
        for m in markers:
            uow.session.delete(m)
        uow.commit()
        
        generate_automatic_logs(uow, user)
        print(f"Logs generated for {user.profile.full_name}. Total logs: {len(user.time_entries)}")
    else:
        print("User not found.")
