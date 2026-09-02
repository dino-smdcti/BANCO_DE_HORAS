from datetime import date

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.domain.model import UserRole
from src.service_layer.accomplishment_service import create_accomplishment
from src.service_layer.idea_service import create_idea, set_idea_status
from src.service_layer.task_service import create_task, update_task_status
from src.service_layer.team_service import list_teams, scoped_update_team, team_rollups
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.user_service import register_user


@pytest.fixture
def uow():
        engine = create_engine("sqlite:///:memory:")
        metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        start_mappers()
        return SqlAlchemyUnitOfWork(session_factory)


def _register_admin(uow):
        register_user(uow, "boss@test.com", "pass", UserRole.GESTOR.value)
        return uow.users.get_user_by_email("boss@test.com").user_id


def _setup_teams(uow, admin):
        from src.service_layer.team_service import create_team
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


def test_scoped_update_team_renames_and_sets_lead(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        lead = _register_actor(uow, "lead@test.com", UserRole.EMPLOYEE.value, team_a)
        scoped_update_team(uow, admin, team_a, name="Time A Renomeado", lead_user_id=str(lead))
        team = uow.users.get_team_by_id(team_a)
        assert team.name == "Time A Renomeado"
        assert team.lead_user_id == lead


def test_scoped_update_team_clear_lead(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        lead = _register_actor(uow, "lead2@test.com", UserRole.EMPLOYEE.value, team_a)
        scoped_update_team(uow, admin, team_a, lead_user_id=str(lead))
        scoped_update_team(uow, admin, team_a, lead_user_id=None)
        assert uow.users.get_team_by_id(team_a).lead_user_id is None


def test_scoped_update_team_denied_duplicate_name(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        with pytest.raises(ValueError):
                scoped_update_team(uow, admin, team_a, name="Time B")


def test_scoped_update_team_denied_out_of_scope(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        manager_a = _register_actor(uow, "mgrD@test.com", UserRole.MANAGER.value, team_a)
        with pytest.raises(PermissionError):
                scoped_update_team(uow, manager_a, team_b, name="Fora do escopo")


def test_team_rollups_counts(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        emp1 = _register_actor(uow, "empD1@test.com", UserRole.EMPLOYEE.value, team_a)
        emp2 = _register_actor(uow, "empD2@test.com", UserRole.EMPLOYEE.value, team_a)
        _register_actor(uow, "empD3@test.com", UserRole.EMPLOYEE.value, team_b)

        create_task(uow, admin, team_id=team_a, title="Tarefa aberta")
        create_accomplishment(uow, admin, team_id=team_a, title="Conquista", start_date=date(2026, 1, 1))
        create_idea(uow, emp1, team_id=team_a, title="Ideia aberta")

        rollups = team_rollups(uow, [team_a])
        data = rollups[team_a]
        assert data["members"] == 2
        assert data["open_tasks"] == 1
        assert data["open_ideas"] == 1
        assert len(data["accomplishments"]) == 1


def test_team_rollups_completed_state_excluded(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        emp1 = _register_actor(uow, "empD4@test.com", UserRole.EMPLOYEE.value, team_a)

        task_id = create_task(uow, admin, team_id=team_a, title="Concluída").task_id
        update_task_status(uow, admin, task_id, "done")
        idea_id = create_idea(uow, emp1, team_id=team_a, title="Implementada").idea_id
        set_idea_status(uow, admin, idea_id, "implemented")

        data = team_rollups(uow, [team_a])[team_a]
        assert data["open_tasks"] == 0
        assert data["open_ideas"] == 0


def test_team_rollups_scoped_by_team_ids(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        create_task(uow, admin, team_id=team_a, title="Tarefa A")
        create_task(uow, admin, team_id=team_b, title="Tarefa B")
        rollups = team_rollups(uow, [team_a])
        assert team_a in rollups
        assert team_b not in rollups


def test_list_teams_still_returns_teams(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        names = [t.name for t in list_teams(uow)]
        assert "Time A" in names