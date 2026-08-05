from datetime import date
from typing import List, Optional
from sqlalchemy import select, update
from werkzeug.security import generate_password_hash

from src.domain.model import User, UserRole, UserProfile, AuditLog
from src.service_layer.unit_of_work import AbstractUnitOfWork
from src.service_layer.permissions import ensure_manager
from src.service_layer.audit import log_action


def register_user(uow: AbstractUnitOfWork, email: str, password: Optional[str] = None, role: str = "employee", registered_by_id: Optional[int] = None) -> bool:
        with uow:
                _create_user(uow, email, password, role, registered_by_id)
        return True


def update_user_profile(uow: AbstractUnitOfWork, user_id: int, registration_number: str, cpf: str, department: str, position: str, secretariat: str, full_name: str, start_analysis_date: Optional[date] = None, birth_date: Optional[date] = None) -> None:
        with uow:
                _apply_profile_update(uow, user_id, registration_number, cpf, department, position, secretariat, full_name, start_analysis_date, birth_date)


def update_credentials(uow: AbstractUnitOfWork, user_id: int, email: str, password: Optional[str] = None, email_notifications_enabled: bool = False):
        with uow:
                _apply_credential_update(uow, user_id, email, password, email_notifications_enabled)


def promote_to_manager(uow: AbstractUnitOfWork, manager_id: int, employee_id: int):
        _change_role(uow, manager_id, employee_id, UserRole.GESTOR, "PROMOTE_USER", "Promovido a Gestor")


def demote_to_employee(uow: AbstractUnitOfWork, manager_id: int, employee_id: int):
        _change_role(uow, manager_id, employee_id, UserRole.EMPLOYEE, "DEMOTE_USER", "Rebaixado a Funcionário")


def delete_user(uow: AbstractUnitOfWork, manager_id: int, user_id: int):
        with uow:
                _perform_delete(uow, manager_id, user_id)


def get_all_employees(uow: AbstractUnitOfWork, requester_id: Optional[int] = None) -> List[User]:
        with uow:
                return _visible_employees(uow, requester_id)


def _create_user(uow, email, password, role, registered_by_id):
        if uow.users.get_user_by_email(email):
                raise ValueError("Email already exists.")
        user = User(email=email, password_hash=_password_hash(password), role=UserRole(role))
        user.profile.start_analysis_date = date.today()
        uow.users.add_user(user)
        log_action(uow, _actor_id(registered_by_id, user), "USER_REGISTERED", target_id=user.user_id, details=f"Nível: {role}")


def _password_hash(password):
        return generate_password_hash(password) if password else "!"


def _actor_id(registered_by_id, user):
        if registered_by_id:
                return int(registered_by_id)
        return user.user_id


def _apply_profile_update(uow, user_id, registration_number, cpf, department, position, secretariat, full_name, start_analysis_date, birth_date):
        user = uow.users.get_user_by_id(user_id)
        if not user:
                raise ValueError("User not found.")
        user.profile = UserProfile(
                registration_number=registration_number,
                cpf=cpf,
                department=department,
                position=position,
                secretariat=secretariat,
                full_name=full_name,
                start_analysis_date=_decide_analysis_date(user.profile.start_analysis_date, start_analysis_date),
                birth_date=_decide_birth_date(user.profile.birth_date, birth_date),
        )
        log_action(uow, user_id, "UPDATE_PROFILE", target_id=user_id, details=f"Matrícula: {registration_number}, Depto: {department}")


def _decide_analysis_date(current, provided):
        return provided or current or date(2026, 1, 1)


def _decide_birth_date(existing, provided):
        """Birthday can only be set once; later changes are ignored."""
        return existing if existing else provided


def _apply_credential_update(uow, user_id, email, password, email_notifications_enabled):
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
        log_action(uow, user_id, "UPDATE_CREDENTIALS", target_id=user_id)


def _change_role(uow, manager_id, employee_id, new_role, action, details):
        with uow:
                ensure_manager(uow, manager_id)
                employee = uow.users.get_user_by_id(employee_id)
                if employee:
                        employee.role = new_role
                        log_action(uow, manager_id, action, target_id=employee_id, details=details)


def _perform_delete(uow, manager_id, user_id):
        ensure_manager(uow, manager_id)
        user = uow.users.get_user_by_id(user_id)
        if not user:
                return
        employee_name = _user_label(user)
        _annotate_audit_logs(uow, user_id, employee_name)
        email = user.email
        uow.session.delete(user)
        log_action(uow, manager_id, "DELETE_USER", target_id=user_id, details=f"Usuário deletado: {email}")


def _user_label(user):
        if user.profile and user.profile.full_name:
                return user.profile.full_name
        return user.email


def _annotate_audit_logs(uow, user_id, employee_name):
        """Preserve the employee's name in audit logs before nullifying their user_id."""
        audit_entries = _audit_logs_for(uow, user_id)
        for audit in audit_entries:
                _append_log_source(audit, employee_name)
        uow.session.flush()
        uow.session.execute(update(AuditLog).where(AuditLog.user_id == user_id).values({AuditLog.user_id: None}))


def _audit_logs_for(uow, user_id):
        return uow.session.execute(select(AuditLog).where(AuditLog.user_id == user_id)).scalars().all()


def _append_log_source(audit, employee_name):
        existing = audit.details or ""
        audit.details = f"{existing} (User: {employee_name})" if existing else f"User: {employee_name}"


def _visible_employees(uow, requester_id):
        if requester_id:
                user = uow.users.get_user_by_id(requester_id)
                if user and user.role in [UserRole.ADMIN, UserRole.GESTOR]:
                        return uow.users.list_all()
        return uow.users.list_employees()
