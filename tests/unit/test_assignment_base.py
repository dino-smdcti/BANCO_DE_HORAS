from unittest.mock import MagicMock
import pytest

from src.domain.model import UserRole
from src.service_layer.permissions import managed_team_ids, scoped_team_ids


class _Team:
    def __init__(self, team_id):
        self.team_id = team_id


def _actor(role, team_id=None):
    return MagicMock(role=role, team_id=team_id)


def _uow_with_users(actor, teams):
    uow = MagicMock()
    uow.users.get_user_by_id.return_value = actor
    uow.users.list_teams.return_value = [_Team(t) for t in teams]
    return uow


def test_managed_team_ids_admin_spans_all_teams():
    uow = _uow_with_users(_actor(UserRole.ADMIN, team_id=7), [1, 2, 3])
    assert managed_team_ids(uow, 1) == [1, 2, 3]


def test_managed_team_ids_gestor_spans_all_teams():
    uow = _uow_with_users(_actor(UserRole.GESTOR, team_id=None), [4, 5])
    assert managed_team_ids(uow, 1) == [4, 5]


def test_managed_team_ids_manager_only_own_team():
    uow = _uow_with_users(_actor(UserRole.MANAGER, team_id=9), [1, 2, 3])
    assert managed_team_ids(uow, 1) == [9]


def test_managed_team_ids_manager_no_team_is_empty():
    uow = _uow_with_users(_actor(UserRole.MANAGER, team_id=None), [1, 2, 3])
    assert managed_team_ids(uow, 1) == []


def test_managed_team_ids_denies_employee():
    uow = _uow_with_users(_actor(UserRole.EMPLOYEE, team_id=9), [1, 2, 3])
    with pytest.raises(PermissionError):
        managed_team_ids(uow, 1)


def test_managed_team_ids_denies_unknown_user():
    uow = _uow_with_users(None, [1, 2, 3])
    with pytest.raises(PermissionError):
        managed_team_ids(uow, 1)


def test_scoped_team_ids_admin_spans_all_teams():
    uow = _uow_with_users(_actor(UserRole.ADMIN, team_id=7), [1, 2])
    assert scoped_team_ids(uow, 1) == [1, 2]


def test_scoped_team_ids_gestor_spans_all_teams():
    uow = _uow_with_users(_actor(UserRole.GESTOR, team_id=7), [1, 2])
    assert scoped_team_ids(uow, 1) == [1, 2]


def test_scoped_team_ids_manager_only_own_team():
    uow = _uow_with_users(_actor(UserRole.MANAGER, team_id=9), [1, 2, 3])
    assert scoped_team_ids(uow, 1) == [9]


def test_scoped_team_ids_employee_sees_only_own_team():
    uow = _uow_with_users(_actor(UserRole.EMPLOYEE, team_id=5), [1, 2, 3])
    assert scoped_team_ids(uow, 1) == [5]


def test_scoped_team_ids_employee_no_team_is_empty():
    uow = _uow_with_users(_actor(UserRole.EMPLOYEE, team_id=None), [1, 2, 3])
    assert scoped_team_ids(uow, 1) == []