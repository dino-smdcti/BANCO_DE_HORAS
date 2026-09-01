from src.domain.model import UserRole
from src.service_layer.unit_of_work import AbstractUnitOfWork


def ensure_manager(uow: AbstractUnitOfWork, manager_id: int):
        """Return the user if they hold a manager-level role, otherwise raise."""
        user = uow.users.get_user_by_id(manager_id)
        if not user or user.role not in [UserRole.MANAGER, UserRole.ADMIN, UserRole.GESTOR]:
                raise PermissionError("Action restricted to managers or admins.")
        return user


def ensure_admin(uow: AbstractUnitOfWork, actor_id: int):
        """Return the user if they hold the admin role, otherwise raise.

        Used for role-changing operations, which are reserved to the admin
        role only (the route layer gates the same operations with
        ``@role_required(ROLE_ADMIN)``).
        """
        user = uow.users.get_user_by_id(actor_id)
        if not user or user.role != UserRole.ADMIN:
                raise PermissionError("Action restricted to administrators.")
        return user


def ensure_not_self(uow: AbstractUnitOfWork, manager_id: int, employee_id: int):
        """Block reviewers from acting on their own time logs unless admin/gestor."""
        if manager_id == employee_id:
                user = uow.users.get_user_by_id(manager_id)
                if not user or user.role not in [UserRole.ADMIN, UserRole.GESTOR]:
                        raise PermissionError("Reviewers cannot review or correct their own time logs. This must be done by an Admin or Gestor.")
