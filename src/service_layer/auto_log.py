from datetime import date, timedelta
from src.domain.model import DailyPonto, PontoStatus, Vacation, Holiday

def generate_automatic_logs(uow, user):
    if not user.work_schedule:
        return

    today = date.today()
    # Check if today is a weekday (0=Mon, 6=Sun)
    if today.weekday() >= 5:
        return

    # Check for holiday
    is_holiday = uow.session.query(Holiday).filter_by(holiday_date=today).first() is not None
    if is_holiday:
        return

    # Check for vacation
    on_vacation = any(v.start_date <= today <= v.end_date for v in user.vacations)
    if on_vacation:
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
