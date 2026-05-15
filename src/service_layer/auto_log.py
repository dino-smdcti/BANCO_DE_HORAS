from datetime import date
from src.domain.model import DailyPonto, PontoStatus, Vacation, Holiday, UserRole

def generate_automatic_logs(uow, user):
    if not user.work_schedule or user.role != UserRole.EMPLOYEE:
        return

    today = date.today()
    
    # Process only weekdays (Mon-Fri)
    if today.weekday() >= 5:
        return

    # Check for holidays or vacations
    is_holiday = uow.session.query(Holiday).filter_by(holiday_date=today).first() is not None
    on_vacation = any(v.start_date <= today <= v.end_date for v in user.vacations)
    
    if is_holiday or on_vacation:
        return

    # Check for existing logs today (if they have logs, we don't need to do anything)
    if any(p.entry_date == today for p in user.time_entries):
        return

    # Create empty placeholder for today
    try:
        new_ponto = DailyPonto(
            user_id=user.user_id,
            entry_date=today,
            status=PontoStatus.ON_TIME,
            location_data="",
            notes=None
        )
        user.time_entries.append(new_ponto)
        uow.session.add(new_ponto)
        uow.commit()
    except Exception:
        uow.session.rollback()
