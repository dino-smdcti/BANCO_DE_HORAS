from datetime import date, timedelta
from src.domain.model import DailyPonto, PontoStatus

def generate_automatic_logs(uow, user):
    if not user.work_schedule:
        return

    today = date.today()
    # Check if today is a weekday (0=Mon, 6=Sun)
    if today.weekday() >= 5:
        return

    # Skip if an entry for today already exists
    if any(p.entry_date == today for p in user.time_entries):
        return

    # Create empty entry
    new_ponto = DailyPonto(
        user_id=user.user_id,
        entry_date=today,
        status=PontoStatus.MISSING,
        location_data="Sistema: Falta automática (dia útil)",
        notes="Ausência sem registro de ponto."
    )
    user.time_entries.append(new_ponto)
    uow.session.add(new_ponto)
    uow.commit()
