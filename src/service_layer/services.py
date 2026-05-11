from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict
from src.domain.model import User, UserRole, UserProfile, DailyPonto, Vacation, Holiday, WorkSchedule, PontoStatus, JourneyType, Notification, AuditLog, CorrectionRequest
from src.service_layer.unit_of_work import AbstractUnitOfWork
from werkzeug.security import generate_password_hash
import pandas as pd
import io

def ensure_manager(uow: AbstractUnitOfWork, manager_id: int):
    user = uow.users.get_user_by_id(manager_id)
    if not user or user.role not in [UserRole.MANAGER, UserRole.ADMIN]:
        raise PermissionError("Action restricted to managers or admins.")
    return user

def ensure_not_self(uow: AbstractUnitOfWork, manager_id: int, employee_id: int):
    if manager_id == employee_id:
        user = uow.users.get_user_by_id(manager_id)
        if not user or user.role != UserRole.ADMIN:
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
    role: str = "employee",
    registered_by_id: Optional[int] = None
) -> bool:
    with uow:
        existing_user = uow.users.get_user_by_email(email)
        if existing_user:
            raise ValueError("Email already exists.")
        
        # If no password provided, use a placeholder
        pw_hash = generate_password_hash(password) if password else "!"
        
        user = User(
            email=email,
            password_hash=pw_hash,
            role=UserRole(role)
        )
        uow.users.add_user(user)
        uow.commit()
        
        actor_id = int(registered_by_id) if registered_by_id else user.user_id
        uow.record_action(actor_id, "USER_REGISTERED", target_id=user.user_id, details=f"Role: {role}")
        uow.commit()
        return True

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

def demote_to_employee(uow: AbstractUnitOfWork, manager_id: int, employee_id: int):
    with uow:
        ensure_manager(uow, manager_id)
        employee = uow.users.get_user_by_id(employee_id)
        if employee:
            employee.role = UserRole.EMPLOYEE
            uow.commit()
            uow.record_action(manager_id, "DEMOTE_USER", target_id=employee_id, details="Demoted to Employee")
            uow.commit()

import math

def calculate_distance(lat1, lon1, lat2, lon2):
    # Haversine formula
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

from src.domain.model import CompanySettings

def get_company_settings(uow: AbstractUnitOfWork) -> Optional[CompanySettings]:
    with uow:
        setting = uow.session.query(CompanySettings).first()
        return setting

def clock_in_out(uow: AbstractUnitOfWork, user_id: int, location: Optional[str] = None, stage: Optional[str] = None, notes: Optional[str] = None) -> str:
    loc = location or "Não obtida"

    with uow:
        user = uow.users.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found.")
        
        # Calculate Brasília Time (UTC-3)
        brazil_time = datetime.utcnow() - timedelta(hours=3)
        today = brazil_time.date()
        now_time = brazil_time.time()

        ponto = next((p for p in user.time_entries if p.entry_date == today), None)
        
        if not stage:
            if not ponto: stage = "arrival"
            elif ponto.has_lunch_break and not ponto.lunch_start: stage = "lunch_start"
            elif ponto.has_lunch_break and not ponto.lunch_end: stage = "lunch_end"
            elif not ponto.departure: stage = "departure"
            else: raise ValueError("Jornada de hoje já está completa.")

        if stage == "arrival":
            if not ponto:
                has_lunch = user.work_schedule.has_lunch_break if user.work_schedule else True
                ponto = DailyPonto(user_id=user_id, entry_date=today, arrival=now_time, has_lunch_break=has_lunch)
                user.time_entries.append(ponto)
            else:
                ponto.arrival = now_time
            ponto.location_data += f" | Chegada: {loc}"
            msg = "Chegada registrada"
            if user.work_schedule:
                limit = (datetime.combine(today, user.work_schedule.expected_arrival) + 
                         timedelta(minutes=user.work_schedule.tolerance_minutes)).time()
                if now_time > limit:
                    ponto.status = PontoStatus.LATE
                    ponto.arrival_late = True
        elif stage == "lunch_start":
            if not ponto: raise ValueError("Registro de chegada não encontrado.")
            ponto.lunch_start = now_time
            ponto.location_data += f" | Almoço (Sai): {loc}"
            msg = "Saída para almoço registrada"
            if user.work_schedule and user.work_schedule.expected_lunch_start:
                limit = (datetime.combine(today, user.work_schedule.expected_lunch_start) - 
                         timedelta(minutes=user.work_schedule.tolerance_minutes)).time()
                if now_time < limit:
                    ponto.status = PontoStatus.LATE
                    ponto.lunch_start_late = True
        elif stage == "lunch_end":
            if not ponto: raise ValueError("Registro de chegada não encontrado.")
            ponto.lunch_end = now_time
            ponto.location_data += f" | Almoço (Vol): {loc}"
            msg = "Retorno do almoço registrado"
            if user.work_schedule and user.work_schedule.expected_lunch_end:
                limit = (datetime.combine(today, user.work_schedule.expected_lunch_end) + 
                         timedelta(minutes=user.work_schedule.tolerance_minutes)).time()
                if now_time > limit:
                    ponto.status = PontoStatus.LATE
                    ponto.lunch_end_late = True
        elif stage == "departure":
            if not ponto: raise ValueError("Registro de chegada não encontrado.")
            ponto.departure = now_time
            ponto.location_data += f" | Fim: {loc}"
            msg = "Fim de jornada registrado"
            if user.work_schedule:
                limit = (datetime.combine(today, user.work_schedule.expected_departure) - 
                         timedelta(minutes=user.work_schedule.tolerance_minutes)).time()
                if now_time < limit:
                    ponto.status = PontoStatus.LATE
                    ponto.departure_early = True
            if notes:
                ponto.notes = notes
        else:
            raise ValueError("Estágio inválido.")
        
        uow.commit()
        uow.record_action(user_id, "CLOCK_EVENT", target_id=user_id, details=f"{msg} ({stage})")
        uow.commit()
        return msg

def submit_correction_request(uow: AbstractUnitOfWork, user_id: int, ponto_date: date, stage: str, proposed_time: time, justification: str):
    with uow:
        req = CorrectionRequest(
            user_id=user_id,
            ponto_date=ponto_date,
            stage=stage,
            proposed_time=proposed_time,
            justification=justification
        )
        uow.session.add(req)
        uow.commit()
        uow.record_action(user_id, "SUBMIT_CORRECTION_REQUEST", target_id=None, details=f"Date: {ponto_date}, Stage: {stage}")
        uow.commit()

def list_pending_corrections(uow: AbstractUnitOfWork, manager_id: int) -> List[CorrectionRequest]:
    with uow:
        ensure_manager(uow, manager_id)
        return uow.session.query(CorrectionRequest).filter_by(status="pending").all()

def review_correction_request(uow: AbstractUnitOfWork, manager_id: int, request_id: int, approved: bool):
    with uow:
        ensure_manager(uow, manager_id)
        req = uow.session.query(CorrectionRequest).filter_by(id=request_id).first()
        if not req:
            raise ValueError("Solicitação não encontrada.")
        
        if approved:
            req.status = "approved"
            user = uow.users.get_user_by_id(req.user_id)
            ponto = next((p for p in user.time_entries if p.entry_date == req.ponto_date), None)
            if not ponto:
                ponto = DailyPonto(user_id=req.user_id, entry_date=req.ponto_date)
                user.time_entries.append(ponto)
            
            if req.stage == "arrival": ponto.arrival = req.proposed_time
            elif req.stage == "lunch_start": ponto.lunch_start = req.proposed_time
            elif req.stage == "lunch_end": ponto.lunch_end = req.proposed_time
            elif req.stage == "departure": ponto.departure = req.proposed_time
            
            ponto.status = PontoStatus.CORRECTED
            ponto.location_data += f" | Corrigido via solicitação aprovada por gestor {manager_id}"
            
            add_notification(uow, req.user_id, f"Sua solicitação de correção para {req.ponto_date} foi APROVADA.")
        else:
            req.status = "rejected"
            add_notification(uow, req.user_id, f"Sua solicitação de correção para {req.ponto_date} foi REJEITADA.")
        
        uow.commit()
        uow.record_action(manager_id, "REVIEW_CORRECTION_REQUEST", target_id=req.user_id, details=f"ReqID: {request_id}, Approved: {approved}")
        uow.commit()

def set_work_schedule(
    uow: AbstractUnitOfWork,
    manager_id: int,
    employee_id: int,
    arrival: time,
    lunch_start: Optional[time],
    lunch_end: Optional[time],
    departure: time,
    tolerance: int = 15,
    has_lunch_break: bool = True
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
            user.work_schedule.has_lunch_break = has_lunch_break
        else:
            user.work_schedule = WorkSchedule(
                user_id=employee_id,
                expected_arrival=arrival,
                expected_lunch_start=lunch_start,
                expected_lunch_end=lunch_end,
                expected_departure=departure,
                tolerance_minutes=tolerance,
                has_lunch_break=has_lunch_break
            )
        uow.commit()
        uow.record_action(manager_id, "SET_WORK_SCHEDULE", target_id=employee_id, details=f"Arrival: {arrival}, Departure: {departure}, Lunch: {has_lunch_break}")
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
        ensure_not_self(uow, manager_id, employee_id)
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
        ensure_not_self(uow, manager_id, employee_id)
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
        ponto.status = PontoStatus.CORRECTED
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

def delete_ponto_entry(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, entry_date: date):
    with uow:
        manager = ensure_manager(uow, manager_id)
        ensure_not_self(uow, manager_id, employee_id)
        user = uow.users.get_user_by_id(employee_id)
        if not user:
            raise ValueError("Employee not found.")
        
        ponto = next((p for p in user.time_entries if p.entry_date == entry_date), None)
        if ponto:
            user.time_entries.remove(ponto)
            uow.session.delete(ponto)
            uow.commit()
            manager_name = manager.profile.full_name or manager.email
            uow.record_action(manager_id, "DELETE_PONTO", target_id=employee_id, details=f"Deleted entry for {entry_date} by {manager_name}")
            uow.commit()

def add_holiday(uow: AbstractUnitOfWork, manager_id: int, holiday_date: date, description: str, is_mandatory: bool = True):
    with uow:
        ensure_manager(uow, manager_id)
        holiday = Holiday(holiday_date=holiday_date, description=description, is_mandatory=is_mandatory)
        uow.session.merge(holiday)
        uow.commit()
        uow.record_action(manager_id, "ADD_HOLIDAY", target_id=None, details=f"Date: {holiday_date}, Desc: {description}")
        uow.commit()

def get_start_analysis_date(uow: AbstractUnitOfWork) -> date:
    with uow:
        settings = uow.session.query(CompanySettings).first()
        return settings.start_analysis_date if settings else date(2026, 1, 1)

def get_all_employees(uow: AbstractUnitOfWork, requester_id: Optional[int] = None) -> List[User]:
    with uow:
        if requester_id:
            user = uow.users.get_user_by_id(requester_id)
            if user and user.role == UserRole.ADMIN:
                return uow.users.list_all()
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
    lunch_start: Optional[time],
    lunch_end: Optional[time],
    departure: time,
    tolerance: int = 15,
    has_lunch_break: bool = True
):
    with uow:
        ensure_manager(uow, manager_id)
        jt = JourneyType(
            name=name,
            expected_arrival=arrival,
            expected_lunch_start=lunch_start,
            expected_lunch_end=lunch_end,
            expected_departure=departure,
            tolerance_minutes=tolerance,
            has_lunch_break=has_lunch_break
        )
        uow.session.add(jt)
        uow.commit()
        uow.record_action(manager_id, "CREATE_JOURNEY_TYPE", target_id=None, details=f"Name: {name}, Lunch: {has_lunch_break}")
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
    lunch_start: Optional[time],
    lunch_end: Optional[time],
    departure: time,
    tolerance: int = 15,
    has_lunch_break: bool = True
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
        jt.has_lunch_break = has_lunch_break
        uow.commit()
        uow.record_action(manager_id, "UPDATE_JOURNEY_TYPE", target_id=journey_id, details=f"Name: {name}, Lunch: {has_lunch_break}")
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

def clear_ponto_anomaly(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, entry_date: date):
    with uow:
        manager = ensure_manager(uow, manager_id)
        user = uow.users.get_user_by_id(employee_id)
        if not user:
            raise ValueError("Employee not found.")
        
        ponto = next((p for p in user.time_entries if p.entry_date == entry_date), None)
        if not ponto:
            raise ValueError("Registro de ponto não encontrado.")
            
        # Limpar flags
        ponto.arrival_late = False
        ponto.lunch_start_late = False
        ponto.lunch_end_late = False
        ponto.departure_early = False
        
        if ponto.status in [PontoStatus.LATE]:
            ponto.status = PontoStatus.ON_TIME
            
        ponto.location_data += f" | Anomalia limpa por: {manager.profile.full_name or manager.email}"
        uow.commit()
        uow.record_action(manager_id, "CLEAR_ANOMALY", target_id=employee_id, details=f"Date: {entry_date}")
        uow.commit()

def dismiss_justification(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, entry_date: date):
    with uow:
        manager = ensure_manager(uow, manager_id)
        user = uow.users.get_user_by_id(employee_id)
        if not user:
            raise ValueError("Employee not found.")
        
        ponto = next((p for p in user.time_entries if p.entry_date == entry_date), None)
        if not ponto or not ponto.has_anomaly:
            raise ValueError("No anomaly found for this date.")
            
        ponto.status = PontoStatus.DISMISSED
        ponto.location_data += f" | Justificativa dispensada por: {manager.profile.full_name or manager.email}"
        uow.commit()
        uow.record_action(manager_id, "DISMISS_JUSTIFICATION", target_id=employee_id, details=f"Date: {entry_date}")
        uow.commit()
