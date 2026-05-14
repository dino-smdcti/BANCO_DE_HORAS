from datetime import date, timedelta
from src.domain.model import DailyPonto, PontoStatus, Vacation, Holiday, CompanySettings, User, UserRole

def generate_automatic_logs(uow, user):
    # Only generate logs for employees
    if user.role != UserRole.EMPLOYEE or not user.work_schedule:
        return

    today = date.today()
    
    # Use a persistent 'auto-log-run' marker log entry to track daily execution
    auto_log_marker = "Sistema: Gerador Automático Executado"
    already_run = any(p.entry_date == today and auto_log_marker in p.location_data for p in user.time_entries)
    if already_run:
        return

    # Use user-specific start analysis date
    start_date = user.profile.start_analysis_date

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
                existing_log_dates.add(current)
        
        current += timedelta(days=1)
    
    # Mark as run today if not already marked
    marker_ponto = next((p for p in user.time_entries if p.entry_date == today and auto_log_marker in p.location_data), None)
    if not marker_ponto:
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
