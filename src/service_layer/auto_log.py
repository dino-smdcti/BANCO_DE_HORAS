from datetime import date
from src.domain.model import DailyPonto, PontoStatus, Vacation, Holiday, UserRole

def generate_automatic_logs(uow, user):
    if not user.work_schedule or user.role != UserRole.EMPLOYEE:
        return

    today = date.today()
    auto_log_marker = "Sistema: Gerador Automático Executado"
    
    # Check if process already ran today for this user
    if any(p.entry_date == today and auto_log_marker in p.location_data for p in user.time_entries):
        return
    
    # Process only weekdays (Mon-Fri)
    if today.weekday() >= 5:
        return

    # Check for holidays or vacations
    is_holiday = uow.session.query(Holiday).filter_by(holiday_date=today).first() is not None
    on_vacation = any(v.start_date <= today <= v.end_date for v in user.vacations)
    
    if is_holiday or on_vacation:
        # Still mark as run even if no log needed, to avoid re-checking
        _mark_as_run(uow, user, today, auto_log_marker)
        return

    # Check for existing logs today
    if any(p.entry_date == today for p in user.time_entries):
        # Already has logs, just mark as run
        _mark_as_run(uow, user, today, auto_log_marker)
        return

    # Create missing entry for today
    try:
        new_ponto = DailyPonto(
            user_id=user.user_id,
            entry_date=today,
            status=PontoStatus.MISSING,
            location_data=f"Sistema: Falta automática | {auto_log_marker}",
            notes="Ausência sem registro de ponto."
        )
        user.time_entries.append(new_ponto)
        uow.session.add(new_ponto)
        uow.commit()
    except Exception:
        uow.session.rollback()

def _mark_as_run(uow, user, today, marker):
    try:
        marker_ponto = DailyPonto(
            user_id=user.user_id,
            entry_date=today,
            status=PontoStatus.ON_TIME,
            location_data=marker,
            notes="Processamento automático diário concluído."
        )
        user.time_entries.append(marker_ponto)
        uow.session.add(marker_ponto)
        uow.commit()
    except Exception:
        uow.session.rollback()
