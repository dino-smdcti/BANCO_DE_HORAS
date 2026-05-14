from datetime import date, timedelta
from src.domain.model import DailyPonto, PontoStatus, Vacation, Holiday, CompanySettings, User, UserRole

def generate_automatic_logs(uow, user):
    if not user.work_schedule or user.role != UserRole.EMPLOYEE:
        return

    today = date.today()
    auto_log_marker = "Sistema: Gerador Automático Executado"
    
    # Ensure session is fresh
    uow.session.refresh(user)
    
    # Persistent check for marker
    already_run = any(p.entry_date == today and auto_log_marker in p.location_data for p in user.time_entries)
    if already_run:
        return

    # Use user-specific start analysis date
    start_date = user.profile.start_analysis_date

    # Get all existing log dates from DB
    existing_log_dates = {p.entry_date for p in user.time_entries}

    current = start_date
    while current < today:
        if current.weekday() < 5:
            is_holiday = uow.session.query(Holiday).filter_by(holiday_date=current).first() is not None
            on_vacation = any(v.start_date <= current <= v.end_date for v in user.vacations)
            
            if not is_holiday and not on_vacation and current not in existing_log_dates:
                try:
                    new_ponto = DailyPonto(
                        user_id=user.user_id,
                        entry_date=current,
                        status=PontoStatus.MISSING,
                        location_data="Sistema: Falta automática (retroativa)",
                        notes="Ausência sem registro de ponto."
                    )
                    user.time_entries.append(new_ponto)
                    uow.session.add(new_ponto)
                    uow.session.flush() # Try flush to catch IntegrityErrors early
                    existing_log_dates.add(current)
                except Exception:
                    uow.session.rollback()
        current += timedelta(days=1)
    
    # Mark as run today
    try:
        marker_ponto = DailyPonto(
            user_id=user.user_id,
            entry_date=today,
            status=PontoStatus.ON_TIME,
            location_data=auto_log_marker,
            notes="Processamento automático diário concluído."
        )
        user.time_entries.append(marker_ponto)
        uow.session.add(marker_ponto)
        uow.commit()
    except Exception:
        uow.session.rollback()
