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

    # Check for existing logs today
    if any(p.entry_date == today for p in user.time_entries):
        return

    # Create missing entry for today
    try:
        new_ponto = DailyPonto(
            user_id=user.user_id,
            entry_date=today,
            status=PontoStatus.MISSING,
            location_data="Sistema: Falta automática (dia atual)",
            notes="Ausência sem registro de ponto."
        )
        user.time_entries.append(new_ponto)
        uow.session.add(new_ponto)
        uow.commit()
    except Exception:
        uow.session.rollback()
