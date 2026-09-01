from unittest.mock import MagicMock
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.orm import metadata, start_mappers
from src.service_layer.permissions import ensure_admin, ensure_manager
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.user_service import demote_to_employee, promote_to_manager, register_user
from src.domain.model import UserRole


def _uow_with(role):
    uow = MagicMock()
    user = MagicMock(role=role)
    uow.users.get_user_by_id.return_value = user
    return uow, user


def test_ensure_manager_allows_manager_level_roles():
    for role in (UserRole.MANAGER, UserRole.ADMIN, UserRole.GESTOR):
        uow, user = _uow_with(role)
        assert ensure_manager(uow, 1) is user


def test_ensure_manager_denies_employee_and_unknown():
    for role in (UserRole.EMPLOYEE, None):
        uow, _ = _uow_with(role)
        with pytest.raises(PermissionError):
            ensure_manager(uow, 1)


def test_ensure_admin_allows_only_admin():
    uow, user = _uow_with(UserRole.ADMIN)
    assert ensure_admin(uow, 1) is user


def test_ensure_admin_denies_manager_gestor_employee():
    for role in (UserRole.MANAGER, UserRole.GESTOR, UserRole.EMPLOYEE, None):
        uow, _ = _uow_with(role)
        with pytest.raises(PermissionError):
            ensure_admin(uow, 1)


def _session_uow():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    start_mappers()
    return SqlAlchemyUnitOfWork(session_factory)


def _create(uow, email, role):
    with uow:
        register_user(uow, email, "pass", role)
        return uow.users.get_user_by_email(email).user_id


def test_promote_requires_admin_at_service_level():
    uow = _session_uow()
    mgr = _create(uow, "mgr_perm@test.com", "manager")
    emp = _create(uow, "emp_perm@test.com", "employee")
    with pytest.raises(PermissionError):
        promote_to_manager(uow, mgr, emp)
    adm = _create(uow, "adm_perm@test.com", "admin")
    promote_to_manager(uow, adm, emp)
    with uow:
        assert uow.users.get_user_by_id(emp).role == UserRole.GESTOR


def test_demote_requires_admin_at_service_level():
    uow = _session_uow()
    mgr = _create(uow, "mgr_perm2@test.com", "manager")
    emp = _create(uow, "emp_perm2@test.com", "gestor")
    with pytest.raises(PermissionError):
        demote_to_employee(uow, mgr, emp)
    adm = _create(uow, "adm_perm2@test.com", "admin")
    demote_to_employee(uow, adm, emp)
    with uow:
        assert uow.users.get_user_by_id(emp).role == UserRole.EMPLOYEE