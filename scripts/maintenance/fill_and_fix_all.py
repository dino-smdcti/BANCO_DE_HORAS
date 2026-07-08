import os
import sys
from datetime import date, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
# Ensure project root is in PYTHONPATH for src imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from src.adapters.orm import start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.domain.model import PontoStatus, DailyPonto, Holiday

# Users to exclude by full name
EXCLUDED_USERS = {"Ana Clara", "Matheus"}

def fill_and_fix_all():
    """Fill missing daily entries and fix incomplete timestamps for all users.

    - Skips users whose full_name is in EXCLUDED_USERS.
    - Uses each user's work schedule to infer expected arrival/departure times.
    - Creates ON_TIME entries for days that are work days and have no record.
    - For existing entries, populates any missing timestamps (arrival, lunch, departure).
    """
    start_mappers()
    # Resolve database URL from environment variables or fallback to local SQLite
    database_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or "sqlite:///banco_de_horas.db"
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    engine = create_engine(database_url)
    uow = SqlAlchemyUnitOfWork(session_factory=sessionmaker(bind=engine))

    today = date.today()
    with uow:
        result = uow.session.execute(text("SELECT holiday_date FROM holidays WHERE is_mandatory = true"))
        holiday_dates = {row[0] for row in result}
        # Iterate over every employee (including managers/gestors)
        users = uow.users.list_all()
        for user in users:
            if user.profile.full_name in EXCLUDED_USERS:
                continue
            if not user.work_schedule:
                continue

            # Determine the start of analysis for this user
            analysis_start = user.profile.start_analysis_date if user.profile else date(2025, 1, 1)
            start_date = max(analysis_start, date(2025, 1, 1))

            # Map existing entries for fast lookup
            existing = {p.entry_date: p for p in user.time_entries}

            current = start_date
            while current <= today:
                # Skip non‑work days, holidays, and vacations
                if not user.work_schedule.is_work_day(current):
                    current += timedelta(days=1)
                    continue
                if current in holiday_dates:
                    current += timedelta(days=1)
                    continue
                if any(v.start_date <= current <= v.end_date for v in user.vacations):
                    current += timedelta(days=1)
                    continue

                ponto = existing.get(current)
                if not ponto:
                    # No entry – create a full ON_TIME record using schedule defaults
                    ponto = DailyPonto(
                        user_id=user.user_id,
                        entry_date=current,
                        arrival=user.work_schedule.expected_arrival,
                        lunch_start=user.work_schedule.expected_lunch_start,
                        lunch_end=user.work_schedule.expected_lunch_end,
                        departure=user.work_schedule.expected_departure,
                        status=PontoStatus.ON_TIME,
                        notes="Preenchimento automático via rotina de manutenção.",
                        location_data="Sistema: Preenchimento automático.",
                        has_lunch_break=user.work_schedule.has_lunch_break,
                    )
                    uow.session.add(ponto)
                    user.time_entries.append(ponto)
                else:
                    # Entry exists – fill missing timestamps
                    changed = False
                    if ponto.arrival is None and user.work_schedule.expected_arrival:
                        ponto.arrival = user.work_schedule.expected_arrival
                        changed = True
                    if user.work_schedule.has_lunch_break:
                        if ponto.lunch_start is None and user.work_schedule.expected_lunch_start:
                            ponto.lunch_start = user.work_schedule.expected_lunch_start
                            changed = True
                        if ponto.lunch_end is None and user.work_schedule.expected_lunch_end:
                            ponto.lunch_end = user.work_schedule.expected_lunch_end
                            changed = True
                    if ponto.departure is None and user.work_schedule.expected_departure:
                        ponto.departure = user.work_schedule.expected_departure
                        changed = True
                    if changed:
                        ponto.status = PontoStatus.ON_TIME
                        ponto.notes = (ponto.notes or "") + " | Correção automática de horários ausentes."
                        ponto.location_data = (ponto.location_data or "") + " | Sistema: Correção automática."
                current += timedelta(days=1)

        uow.commit()
        print("Rotina de preenchimento concluída.")

if __name__ == "__main__":
    fill_and_fix_all()
