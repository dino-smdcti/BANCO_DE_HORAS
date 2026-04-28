from datetime import datetime, date, time
from typing import Optional, List, Dict
from src.domain.model import User, UserRole, UserProfile, DailyPonto, Vacation, Holiday
from src.service_layer.unit_of_work import AbstractUnitOfWork
from werkzeug.security import generate_password_hash
import pandas as pd
import io

def ensure_manager(uow: AbstractUnitOfWork, manager_id: int):
    user = uow.users.get_user_by_id(manager_id)
    if not user or user.role != UserRole.MANAGER:
        raise PermissionError("Action restricted to managers.")

def register_user(
    uow: AbstractUnitOfWork, 
    email: str, 
    password: str, 
    role: str = "employee"
) -> None:
    with uow:
        existing_user = uow.users.get_user_by_email(email)
        if existing_user:
            raise ValueError(f"User with email {email} already exists.")
        
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role=UserRole(role)
        )
        uow.users.add_user(user)
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

def update_credentials(uow: AbstractUnitOfWork, user_id: int, email: str, password: Optional[str] = None):
    with uow:
        user = uow.users.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found.")
        
        existing = uow.users.get_user_by_email(email)
        if existing and existing.user_id != user_id:
            raise ValueError("Email already in use.")
            
        user.email = email
        if password:
            user.password_hash = generate_password_hash(password)
        uow.commit()

def promote_to_manager(uow: AbstractUnitOfWork, manager_id: int, employee_id: int):
    with uow:
        ensure_manager(uow, manager_id)
        employee = uow.users.get_user_by_id(employee_id)
        if employee:
            employee.role = UserRole.MANAGER
            uow.commit()

def clock_in_out(uow: AbstractUnitOfWork, user_id: int, location: Optional[str] = None) -> str:
    with uow:
        user = uow.users.get_user_by_id(user_id)
        today = date.today()
        now_time = datetime.now().time()

        ponto = next((p for p in user.time_entries if p.entry_date == today), None)
        
        if not ponto:
            ponto = DailyPonto(user_id=user_id, entry_date=today, arrival=now_time)
            ponto.location_data = f"Chegada: {location or 'Desconhecido'}"
            user.time_entries.append(ponto)
            msg = "Chegada registrada"
        elif not ponto.lunch_start:
            ponto.lunch_start = now_time
            ponto.location_data += f" | Almoço (Sai): {location or 'Desconhecido'}"
            msg = "Saída para almoço registrada"
        elif not ponto.lunch_end:
            ponto.lunch_end = now_time
            ponto.location_data += f" | Almoço (Vol): {location or 'Desconhecido'}"
            msg = "Retorno do almoço registrado"
        elif not ponto.departure:
            ponto.departure = now_time
            ponto.location_data += f" | Fim: {location or 'Desconhecido'}"
            msg = "Fim de jornada registrado"
        else:
            raise ValueError("Jornada de hoje já está completa.")
        
        uow.commit()
        return msg

def manual_ponto_correction(
    uow: AbstractUnitOfWork, 
    manager_id: int, 
    employee_id: int, 
    entry_date: date,
    arrival: Optional[time],
    lunch_start: Optional[time],
    lunch_end: Optional[time],
    departure: Optional[time]
):
    with uow:
        ensure_manager(uow, manager_id)
        user = uow.users.get_user_by_id(employee_id)
        ponto = next((p for p in user.time_entries if p.entry_date == entry_date), None)
        
        if not ponto:
            ponto = DailyPonto(user_id=employee_id, entry_date=entry_date)
            user.time_entries.append(ponto)
        
        ponto.arrival = arrival
        ponto.lunch_start = lunch_start
        ponto.lunch_end = lunch_end
        ponto.departure = departure
        ponto.location_data += f" | Corrigido manualmente por Gestor ID {manager_id}"
        uow.commit()

def generate_excel_report(uow: AbstractUnitOfWork, user_id: int) -> io.BytesIO:
    with uow:
        user = uow.users.get_user_by_id(user_id)
        data = []
        for p in user.time_entries:
            data.append({
                "Data": p.entry_date,
                "Chegada": p.arrival.strftime("%H:%M:%S") if p.arrival else "-",
                "Almoço (Sai)": p.lunch_start.strftime("%H:%M:%S") if p.lunch_start else "-",
                "Almoço (Vol)": p.lunch_end.strftime("%H:%M:%S") if p.lunch_end else "-",
                "Fim": p.departure.strftime("%H:%M:%S") if p.departure else "-",
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
        employee.vacations.append(vacation)
        uow.commit()

def add_holiday(uow: AbstractUnitOfWork, manager_id: int, holiday_date: date, description: str, is_mandatory: bool):
    with uow:
        ensure_manager(uow, manager_id)
        holiday = Holiday(holiday_date=holiday_date, description=description, is_mandatory=is_mandatory)
        uow.session.add(holiday)
        uow.commit()

def get_all_employees(uow: AbstractUnitOfWork) -> List[User]:
    with uow:
        return uow.users.list_employees()

def delete_user(uow: AbstractUnitOfWork, manager_id: int, user_id: int):
    with uow:
        ensure_manager(uow, manager_id)
        user = uow.users.get_user_by_id(user_id)
        if user:
            uow.session.delete(user)
            uow.commit()
