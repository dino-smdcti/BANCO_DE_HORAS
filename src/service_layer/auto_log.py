from datetime import date, timedelta
from src.domain.model import DailyPonto, PontoStatus, Vacation, Holiday, CompanySettings, User

def generate_automatic_logs(uow, user):
    if not user.work_schedule:
        return

    today = date.today()
    
    # Track last execution date in a hidden metadata column or a simple check
    # For simplicity, we'll store a 'last_auto_log_date' in user.profile or add it to User/Profile if possible.
    # Since we can't easily modify the DB schema now, we'll check against a system setting or a file.
    # Actually, a simpler way: if we have today's 'system log entry', skip.
    # But let's check the database for the latest auto-log date.
    
    last_run = getattr(user, 'last_auto_log_date', None)
    if last_run == today:
        return

    # Get start analysis date
    settings = uow.session.query(CompanySettings).first()
    start_date = settings.start_analysis_date if settings else date(2026, 1, 1)

    # Get all existing log dates for the user
    existing_log_dates = {p.entry_date for p in user.time_entries}

    current = start_date
    while current < today:
        # Check if weekday
        if current.weekday() < 5:
            # Check for holiday
            is_holiday = uow.session.query(Holiday).filter_by(holiday_date=current).first() is not None
            
            # Check for vacation
            on_vacation = any(v.start_date <= current <= v.end_date for v in user.vacations)
            
            if not is_holiday and not on_vacation and current not in existing_log_dates:
                # Create missing entry
                new_ponto = DailyPonto(
                    user_id=user.user_id,
                    entry_date=current,
                    status=PontoStatus.MISSING,
                    location_data="Sistema: Falta automática (retroativa)",
                    notes="Ausência sem registro de ponto."
                )
                user.time_entries.append(new_ponto)
                uow.session.add(new_ponto)
        
        current += timedelta(days=1)
    
    user.last_auto_log_date = today
    uow.commit()
