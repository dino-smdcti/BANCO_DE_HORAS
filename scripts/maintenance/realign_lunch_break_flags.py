import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork

def realign_lunch_break_flags():
    """
    Sync daily_pontos.has_lunch_break with the user's work_schedule.has_lunch_break.

    The per-entry flag is a snapshot taken when the log was created and can drift
    when a schedule changes (or via bulk imports). Balance math now treats the
    schedule as the source of truth, but the stored flag still feeds the per-day
    worked-minutes display, so realigning it keeps logs consistent.
    """
    load_dotenv()
    start_mappers()
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or "sqlite:///banco_de_horas.db"
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    engine = create_engine(database_url)
    uow = SqlAlchemyUnitOfWork(session_factory=sessionmaker(bind=engine))

    with uow:
        updated = 0
        for user in uow.users.list_all():
            if not user.work_schedule:
                continue
            expected = user.work_schedule.has_lunch_break
            for ponto in user.time_entries:
                if ponto.has_lunch_break != expected:
                    print(
                        f"user={user.user_id} {user.email} | {ponto.entry_date} | "
                        f"has_lunch_break {ponto.has_lunch_break} -> {expected}"
                    )
                    ponto.has_lunch_break = expected
                    updated += 1
        uow.commit()
        print(f"Realigned {updated} daily_pontos row(s).")

if __name__ == "__main__":
    realign_lunch_break_flags()
