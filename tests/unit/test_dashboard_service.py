from datetime import date

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.domain.model import UserRole
from src.service_layer.culture_service import give_kudo
from src.service_layer.dashboard_service import dashboard_metrics
from src.service_layer.idea_service import create_idea
from src.service_layer.s5_service import create_s5_audit
from src.service_layer.task_service import create_task, update_task_status
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


def _register_admin(uow):
        register_user(uow, "boss@test.com", "pass", UserRole.GESTOR.value)
        return uow.users.get_user_by_email("boss@test.com").user_id


def _register_actor(uow, email, role, team_id):
        register_user(uow, email, "pass", role)
        user = uow.users.get_user_by_email(email)
        with uow:
                uow.users.set_user_team(user.user_id, team_id)
                uow.commit()
        return user.user_id


def test_dashboard_metrics_aggregates_scoped_teams(uow):
        admin = _register_admin(uow)
        create_team(uow, admin, "Time A")
        team_a = uow.users.get_team_by_name("Time A").team_id
        author = _register_actor(uow, "a@test.com", UserRole.EMPLOYEE.value, team_a)
        peer = _register_actor(uow, "b@test.com", UserRole.EMPLOYEE.value, team_a)

        task = create_task(uow, admin, team_id=team_a, title="Tarefa", assignee_id=author)
        update_task_status(uow, admin, task.task_id, "in_execution")
        create_idea(uow, author, title="Ideia", team_id=team_a)
        give_kudo(uow, peer, team_id=team_a, receiver_id=author, message="Boa!")
        create_s5_audit(uow, admin, team_id=team_a, date=date(2026, 1, 1), passed_ids=[0, 1, 2, 3])

        metrics = dashboard_metrics(uow, admin)

        stages = {s["label"]: s["value"] for s in metrics["task_stage_counts"]}
        assert stages["Em Execução"] == 1

        ideas = {s["label"]: s["value"] for s in metrics["idea_status_counts"]}
        assert ideas["Aberta"] == 1

        likes = {s["label"]: s["value"] for s in metrics["likes_by_team"]}
        assert likes["Time A"] == 1

        assert metrics["s5_trend"][0]["avg"] == 80.0


def test_dashboard_metrics_empty_scope(uow):
        admin = _register_admin(uow)
        metrics = dashboard_metrics(uow, admin)
        assert all(s["value"] == 0 for s in metrics["task_stage_counts"])
        assert all(s["value"] == 0 for s in metrics["idea_status_counts"])
        assert metrics["likes_by_team"] == []
        assert metrics["s5_trend"] == []
