from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict
from src.domain.model import User, UserRole, UserProfile, DailyPonto, Vacation, Holiday, WorkSchedule, PontoStatus, JourneyType, Notification
from src.service_layer.unit_of_work import AbstractUnitOfWork
from werkzeug.security import generate_password_hash
import pandas as pd
import io

def ensure_manager(uow: AbstractUnitOfWork, manager_id: int):
    user = uow.users.get_user_by_id(manager_id)
    if not user or user.role not in [UserRole.MANAGER, UserRole.ADMIN]:
        raise PermissionError("Action restricted to managers or admins.")
    return user

def ensure_not_self(manager_id: int, employee_id: int):
    if manager_id == employee_id:
        raise PermissionError("Reviewers cannot review or correct their own time logs. This must be done by an Admin.")

def add_notification(uow: AbstractUnitOfWork, user_id: int, message: str, email_sender=None):
    notification = Notification(user_id=user_id, message=message, created_at=datetime.now())
    uow.session.add(notification)
    
    # Send email if enabled
    user = uow.users.get_user_by_id(user_id)
    if user and user.email_notifications_enabled and email_sender:
        email_sender(user.email, "Nova Notificação - Banco de Horas", f"<p>{message}</p>")

def mark_notifications_as_read(uow: AbstractUnitOfWork, user_id: int):
    with uow:
        user = uow.users.get_user_by_id(user_id)
        if user:
            for n in user.notifications:
                n.is_read = True
            uow.commit()

def register_user(
    uow: AbstractUnitOfWork, 
    email: str, 
    password: Optional[str] = None, 
    role: str = "employee"
) -> None:
    with uow:
        existing_user = uow.users.get_user_by_email(email)
        if existing_user:
            raise ValueError(f"User with email {email} already exists.")
        
        # If no password provided, use a placeholder
        pw_hash = generate_password_hash(password) if password else "!"
        
        user = User(
            email=email,
            password_hash=pw_hash,
            role=UserRole(role)
        )
        uow.users.add_user(user)
        uow.commit()
        # Note: manager_id is not passed here, would need to update signature if we want to log who registered
        uow.record_action(user.user_id, "USER_REGISTERED", target_id=user.user_id, details=f"Role: {role}")
        uow.commit()

def update_user_profile(
    uow: AbstractUnitOfWork,
    user_id: int,
    registration_number: str,
    cpf: str,
    department: str,
    position: str,
    secretariat: str,
    full_name: str
) -> None:
    with uow:
        user = uow.users.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found.")
        
        new_profile = UserProfile(
            registration_number=registration_number,
            cpf=cpf,
            department=department,
            position=position,
            secretariat=secretariat,
            full_name=full_name
        )
        user.profile = new_profile
        uow.commit()
        uow.record_action(user_id, "UPDATE_PROFILE", target_id=user_id, details=f"Registration: {registration_number}, Dept: {department}")
        uow.commit()

def update_credentials(uow: AbstractUnitOfWork, user_id: int, email: str, password: Optional[str] = None, email_notifications_enabled: bool = False):
    with uow:
        user = uow.users.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found.")
        
        existing = uow.users.get_user_by_email(email)
        if existing and existing.user_id != user_id:
            raise ValueError("Email already in use.")
            
        user.email = email
        user.email_notifications_enabled = email_notifications_enabled
        if password:
            user.password_hash = generate_password_hash(password)
        uow.commit()
        uow.record_action(user_id, "UPDATE_CREDENTIALS", target_id=user_id)
        uow.commit()

def promote_to_manager(uow: AbstractUnitOfWork, manager_id: int, employee_id: int):
    with uow:
        ensure_manager(uow, manager_id)
        employee = uow.users.get_user_by_id(employee_id)
        if employee:
            employee.role = UserRole.MANAGER
            uow.commit()
            uow.record_action(manager_id, "PROMOTE_USER", target_id=employee_id, details="Promoted to Manager")
            uow.commit()

def clock_in_out(uow: AbstractUnitOfWork, user_id: int, location: Optional[str] = None) -> str:
    with uow:
        user = uow.users.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found.")
        today = date.today()
        now_time = datetime.now().time()

        ponto = next((p for p in user.time_entries if p.entry_date == today), None)
        
        if not ponto:
            ponto = DailyPonto(user_id=user_id, entry_date=today, arrival=now_time)
            ponto.location_data = f"Chegada: {location or 'Desconhecido'}"
            user.time_entries.append(ponto)
            msg = "Chegada registrada"
            # Check for lateness on arrival
            if user.work_schedule:
                limit = (datetime.combine(today, user.work_schedule.expected_arrival) + 
                         timedelta(minutes=user.work_schedule.tolerance_minutes)).time()
                if now_time > limit:
                    ponto.status = PontoStatus.LATE
                    ponto.arrival_late = True
        elif not ponto.lunch_start:
            ponto.lunch_start = now_time
            ponto.location_data += f" | Almoço (Sai): {location or 'Desconhecido'}"
            msg = "Saída para almoço registrada"
            # Check for early lunch (optional, but good for completeness)
            if user.work_schedule:
                limit = (datetime.combine(today, user.work_schedule.expected_lunch_start) - 
                         timedelta(minutes=user.work_schedule.tolerance_minutes)).time()
                if now_time < limit:
                    ponto.status = PontoStatus.LATE
                    ponto.lunch_start_late = True # Using 'late' flag for any anomaly
        elif not ponto.lunch_end:
            ponto.lunch_end = now_time
            ponto.location_data += f" | Almoço (Vol): {location or 'Desconhecido'}"
            msg = "Retorno do almoço registrado"
            # Check for lateness on return from lunch
            if user.work_schedule:
                limit = (datetime.combine(today, user.work_schedule.expected_lunch_end) + 
                         timedelta(minutes=user.work_schedule.tolerance_minutes)).time()
                if now_time > limit:
                    ponto.status = PontoStatus.LATE
                    ponto.lunch_end_late = True
        elif not ponto.departure:
            ponto.departure = now_time
            ponto.location_data += f" | Fim: {location or 'Desconhecido'}"
            msg = "Fim de jornada registrado"
            # Check for early departure
            if user.work_schedule:
                limit = (datetime.combine(today, user.work_schedule.expected_departure) - 
                         timedelta(minutes=user.work_schedule.tolerance_minutes)).time()
                if now_time < limit:
                    ponto.status = PontoStatus.LATE
                    ponto.departure_early = True
        else:
            raise ValueError("Jornada de hoje já está completa.")
        
        uow.commit()
        uow.record_action(user_id, "CLOCK_EVENT", target_id=user_id, details=msg)
        uow.commit()
        return msg

def set_work_schedule(
    uow: AbstractUnitOfWork,
    manager_id: int,
    employee_id: int,
    arrival: time,
    lunch_start: time,
    lunch_end: time,
    departure: time,
    tolerance: int = 15
):
    with uow:
        user = uow.users.get_user_by_id(employee_id)
        if not user:
            raise ValueError("Employee not found.")

        # Allow self-assignment ONLY if no schedule exists
        if manager_id == employee_id:
            if user.work_schedule:
                raise PermissionError("Self-reassignment not allowed. Contact a manager.")
        else:
            ensure_manager(uow, manager_id)
        
        if user.work_schedule:
            user.work_schedule.expected_arrival = arrival
            user.work_schedule.expected_lunch_start = lunch_start
            user.work_schedule.expected_lunch_end = lunch_end
            user.work_schedule.expected_departure = departure
            user.work_schedule.tolerance_minutes = tolerance
        else:
            user.work_schedule = WorkSchedule(
                user_id=employee_id,
                expected_arrival=arrival,
                expected_lunch_start=lunch_start,
                expected_lunch_end=lunch_end,
                expected_departure=departure,
                tolerance_minutes=tolerance
            )
        uow.commit()
        uow.record_action(manager_id, "SET_WORK_SCHEDULE", target_id=employee_id, details=f"Arrival: {arrival}, Departure: {departure}")
        uow.commit()

def generate_missing_logs(uow: AbstractUnitOfWork, manager_id: int, target_date: date):
    with uow:
        ensure_manager(uow, manager_id)
        employees = uow.users.list_employees()
        
        for emp in employees:
            ponto = next((p for p in emp.time_entries if p.entry_date == target_date), None)
            if not ponto:
                # Check if user has vacation on this date
                on_vacation = any(v.start_date <= target_date <= v.end_date for v in emp.vacations)
                if on_vacation:
                    continue
                
                # Create missing log
                ponto = DailyPonto(
                    user_id=emp.user_id,
                    entry_date=target_date,
                    status=PontoStatus.MISSING,
                    location_data="Sistema: Falta detectada"
                )
                emp.time_entries.append(ponto)
        uow.commit()

def review_justification(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, entry_date: date, approved: bool, email_sender=None):
    with uow:
        manager = ensure_manager(uow, manager_id)
        ensure_not_self(manager_id, employee_id)
        user = uow.users.get_user_by_id(employee_id)
        if not user:
            raise ValueError("Employee not found.")
        
        ponto = next((p for p in user.time_entries if p.entry_date == entry_date), None)
        if not ponto or not ponto.has_anomaly:
            raise ValueError("No anomaly found for this date to justify.")
        
        manager_name = manager.profile.full_name or manager.email
        if approved:
            ponto.status = PontoStatus.JUSTIFIED
            ponto.location_data += f" | Justificativa APROVADA por Gestor: {manager_name}"
            msg = f"Sua justificativa para o dia {entry_date} foi APROVADA pelo gestor {manager_name}."
        else:
            ponto.status = PontoStatus.REJECTED
            ponto.location_data += f" | Justificativa REJEITADA por Gestor: {manager_name}"
            msg = f"Sua justificativa para o dia {entry_date} foi REJEITADA pelo gestor {manager_name}."
        
        add_notification(uow, employee_id, msg, email_sender=email_sender)
        uow.commit()
        uow.record_action(manager_id, "REVIEW_JUSTIFICATION", target_id=employee_id, details=f"Date: {entry_date}, Approved: {approved}")
        uow.commit()

def manual_ponto_correction(
    uow: AbstractUnitOfWork, 
    manager_id: int, 
    employee_id: int, 
    entry_date: date,
    arrival: Optional[time],
    lunch_start: Optional[time],
    lunch_end: Optional[time],
    departure: Optional[time],
    email_sender=None
):
    with uow:
        manager = ensure_manager(uow, manager_id)
        ensure_not_self(manager_id, employee_id)
        user = uow.users.get_user_by_id(employee_id)
        if not user:
            raise ValueError("Employee not found.")
        ponto = next((p for p in user.time_entries if p.entry_date == entry_date), None)
        
        if not ponto:
            ponto = DailyPonto(user_id=employee_id, entry_date=entry_date)
            user.time_entries.append(ponto)
        
        ponto.arrival = arrival
        ponto.lunch_start = lunch_start
        ponto.lunch_end = lunch_end
        ponto.departure = departure
        manager_name = manager.profile.full_name or manager.email
        ponto.location_data += f" | Corrigido manualmente por Gestor: {manager_name}"
        
        add_notification(uow, employee_id, f"Seu ponto de {entry_date} foi corrigido manualmente pelo gestor {manager_name}.", email_sender=email_sender)
        uow.commit()
        uow.record_action(manager_id, "MANUAL_CORRECTION", target_id=employee_id, details=f"Date: {entry_date}")
        uow.commit()

def generate_excel_report(uow: AbstractUnitOfWork, user_id: int) -> io.BytesIO:
    with uow:
        user = uow.users.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found.")
        data = []
        for p in user.time_entries:
            data.append({
                "Data": p.entry_date.strftime("%d/%m/%Y"),
                "Chegada": p.arrival.strftime("%H:%M:%S") if p.arrival else "-",
                "Almoço (Sai)": p.lunch_start.strftime("%H:%M:%S") if p.lunch_start else "-",
                "Almoço (Vol)": p.lunch_end.strftime("%H:%M:%S") if p.lunch_end else "-",
                "Fim": p.departure.strftime("%H:%M:%S") if p.departure else "-",
                "Status": p.status.value,
                "Justificativa": p.justification or "-",
                "Minutos Trabalhados": p.worked_minutes,
                "Localização": p.location_data
            })
        
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Banco de Horas")
        output.seek(0)
        return output

def add_vacation(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, start_date: date, end_date: date):
    with uow:
        ensure_manager(uow, manager_id)
        vacation = Vacation(user_id=employee_id, start_date=start_date, end_date=end_date)
        employee = uow.users.get_user_by_id(employee_id)
        if not employee:
            raise ValueError("Employee not found.")
        employee.vacations.append(vacation)
        uow.commit()
        uow.record_action(manager_id, "ADD_VACATION", target_id=employee_id, details=f"Start: {start_date}, End: {end_date}")
        uow.commit()

def add_holiday(uow: AbstractUnitOfWork, manager_id: int, holiday_date: date, description: str, is_mandatory: bool):
    with uow:
        ensure_manager(uow, manager_id)
        holiday = Holiday(holiday_date=holiday_date, description=description, is_mandatory=is_mandatory)
        uow.session.add(holiday)
        uow.commit()
        uow.record_action(manager_id, "ADD_HOLIDAY", target_id=None, details=f"Date: {holiday_date}, Desc: {description}")
        uow.commit()

def get_all_employees(uow: AbstractUnitOfWork) -> List[User]:
    with uow:
        return uow.users.list_employees()

def delete_user(uow: AbstractUnitOfWork, manager_id: int, user_id: int):
    with uow:
        ensure_manager(uow, manager_id)
        user = uow.users.get_user_by_id(user_id)
        if user:
            email = user.email
            uow.session.delete(user)
            uow.commit()
            uow.record_action(manager_id, "DELETE_USER", target_id=user_id, details=f"Deleted user: {email}")
            uow.commit()

def create_journey_type(
    uow: AbstractUnitOfWork,
    manager_id: int,
    name: str,
    arrival: time,
    lunch_start: time,
    lunch_end: time,
    departure: time,
    tolerance: int = 15
):
    with uow:
        ensure_manager(uow, manager_id)
        jt = JourneyType(
            name=name,
            expected_arrival=arrival,
            expected_lunch_start=lunch_start,
            expected_lunch_end=lunch_end,
            expected_departure=departure,
            tolerance_minutes=tolerance
        )
        uow.session.add(jt)
        uow.commit()
        uow.record_action(manager_id, "CREATE_JOURNEY_TYPE", target_id=None, details=f"Name: {name}")
        uow.commit()

def list_journey_types(uow: AbstractUnitOfWork) -> List[JourneyType]:
    with uow:
        return uow.session.query(JourneyType).all()

def get_journey_type(uow: AbstractUnitOfWork, journey_id: int) -> Optional[JourneyType]:
    with uow:
        return uow.session.query(JourneyType).filter_by(journey_id=journey_id).first()

def update_journey_type(
    uow: AbstractUnitOfWork,
    manager_id: int,
    journey_id: int,
    name: str,
    arrival: time,
    lunch_start: time,
    lunch_end: time,
    departure: time,
    tolerance: int = 15
):
    with uow:
        ensure_manager(uow, manager_id)
        jt = uow.session.query(JourneyType).filter_by(journey_id=journey_id).first()
        if not jt:
            raise ValueError("Journey Type not found.")
        
        jt.name = name
        jt.expected_arrival = arrival
        jt.expected_lunch_start = lunch_start
        jt.expected_lunch_end = lunch_end
        jt.expected_departure = departure
        jt.tolerance_minutes = tolerance
        uow.commit()
        uow.record_action(manager_id, "UPDATE_JOURNEY_TYPE", target_id=journey_id, details=f"Name: {name}")
        uow.commit()

def delete_journey_type(uow: AbstractUnitOfWork, manager_id: int, journey_id: int):
    with uow:
        ensure_manager(uow, manager_id)
        jt = uow.session.query(JourneyType).filter_by(journey_id=journey_id).first()
        if jt:
            name = jt.name
            uow.session.delete(jt)
            uow.commit()
            uow.record_action(manager_id, "DELETE_JOURNEY_TYPE", target_id=journey_id, details=f"Deleted: {name}")
            uow.commit()

def submit_justification(uow: AbstractUnitOfWork, user_id: int, entry_date: date, justification: str):
    with uow:
        user = uow.users.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found.")
        
        ponto = next((p for p in user.time_entries if p.entry_date == entry_date), None)
        if not ponto:
             ponto = DailyPonto(user_id=user_id, entry_date=entry_date, status=PontoStatus.MISSING)
             user.time_entries.append(ponto)
        
        ponto.justification = justification
        uow.commit()
        uow.record_action(user_id, "SUBMIT_JUSTIFICATION", target_id=user_id, details=f"Date: {entry_date}")
        uow.commit()
