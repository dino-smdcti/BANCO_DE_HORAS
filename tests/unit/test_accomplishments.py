from datetime import date

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.domain.model import UserRole
from src.service_layer.accomplishment_service import (
        create_accomplishment,
        delete_accomplishment,
        edit_accomplishment,
        get_accomplishment,
        list_accomplishments,
)
from src.service_layer.team_service import create_team
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.user_service import register_user


@pytest.fixture
def uow():
        engine = create_engine("sqlite:///:memory:")
        metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        start_mappers()
        return SqlAlchemyUnitOfWork(session_factory)


def _setup_teams(uow, admin):
        create_team(uow, admin, "Time A")
        create_team(uow, admin, "Time B")
        team_a = uow.users.get_team_by_name("Time A").team_id
        team_b = uow.users.get_team_by_name("Time B").team_id
        return team_a, team_b


def _register_actor(uow, email, role, team_id):
        register_user(uow, email, "pass", role)
        user = uow.users.get_user_by_email(email)
        with uow:
                uow.users.set_user_team(user.user_id, team_id)
                uow.commit()
        return user.user_id


def _register_admin(uow):
        register_user(uow, "boss@test.com", "pass", UserRole.GESTOR.value)
        return uow.users.get_user_by_email("boss@test.com").user_id


def _create(uow, admin, team_id, title, **kwargs):
        with uow:
                acc = create_accomplishment(
                        uow, admin, team_id=team_id, title=title,
                        start_date=kwargs.get("start_date", date(2026, 1, 1)),
                        end_date=kwargs.get("end_date"),
                        achieved_by_user_id=kwargs.get("achieved_by_user_id"),
                )
                return acc.accomplishment_id


def _acc(uow, acc_id):
        with uow:
                return uow.users.get_accomplishment_by_id(acc_id)


def test_create_accomplishment_requires_title(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        with pytest.raises(ValueError):
                create_accomplishment(uow, admin, team_id=team_a, title="   ", start_date=date(2026, 1, 1))


def test_create_accomplishment_requires_start_date(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        with pytest.raises(ValueError):
                create_accomplishment(uow, admin, team_id=team_a, title="Sem início", start_date=None)


def test_create_accomplishment_rejects_end_before_start(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        with pytest.raises(ValueError):
                create_accomplishment(
                        uow, admin, team_id=team_a, title="Período inválido",
                        start_date=date(2026, 5, 1), end_date=date(2026, 1, 1),
                )


def test_create_accomplishment_denied_out_of_scope_team(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        manager = _register_actor(uow, "mgrA@test.com", UserRole.MANAGER.value, team_a)
        with pytest.raises(PermissionError):
                create_accomplishment(uow, manager, team_id=team_b, title="Fora do escopo", start_date=date(2026, 1, 1))


def test_create_accomplishment_denied_for_employee(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        employee = _register_actor(uow, "emp2@test.com", UserRole.EMPLOYEE.value, team_a)
        with pytest.raises(PermissionError):
                create_accomplishment(uow, employee, team_id=team_a, title="Sem permissão", start_date=date(2026, 1, 1))


def test_list_accomplishments_scoped(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        _create(uow, admin, team_a, "Conquista A")
        _create(uow, admin, team_b, "Conquista B")
        manager_a = _register_actor(uow, "mgrB@test.com", UserRole.MANAGER.value, team_a)
        titles = [a.title for a in list_accomplishments(uow, manager_a)]
        assert "Conquista A" in titles
        assert "Conquista B" not in titles


def test_get_accomplishment_visible_to_team(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        acc_id = _create(uow, admin, team_a, "Minha conquista")
        employee = _register_actor(uow, "empV@test.com", UserRole.EMPLOYEE.value, team_a)
        assert get_accomplishment(uow, employee, acc_id).title == "Minha conquista"

        outsider = _register_actor(uow, "empX@test.com", UserRole.EMPLOYEE.value, team_b)
        with pytest.raises(PermissionError):
                get_accomplishment(uow, outsider, acc_id)


def test_edit_accomplishment_manager_only(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        assignee = _register_actor(uow, "empE@test.com", UserRole.EMPLOYEE.value, team_a)
        acc_id = _create(uow, admin, team_a, "Original")
        edit_accomplishment(uow, admin, acc_id, title="Editada", end_date=date(2026, 2, 1))
        assert _acc(uow, acc_id).title == "Editada"
        assert _acc(uow, acc_id).end_date == date(2026, 2, 1)

        with pytest.raises(PermissionError):
                edit_accomplishment(uow, assignee, acc_id, title="Sem permissão")


def test_edit_accomplishment_reopens_with_clear_end_date(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        acc_id = _create(uow, admin, team_a, "Fechada", end_date=date(2026, 3, 1))
        edit_accomplishment(uow, admin, acc_id, clear_end_date=True)
        assert _acc(uow, acc_id).end_date is None


def test_delete_accomplishment_manager_only(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        assignee = _register_actor(uow, "empD@test.com", UserRole.EMPLOYEE.value, team_a)
        acc_id = _create(uow, admin, team_a, "Excluir")
        with pytest.raises(PermissionError):
                delete_accomplishment(uow, assignee, acc_id)
        delete_accomplishment(uow, admin, acc_id)
        assert _acc(uow, acc_id) is None