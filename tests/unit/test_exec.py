from datetime import date

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.domain.model import UserRole
from src.service_layer.accomplishment_service import create_accomplishment
from src.service_layer.exec_service import list_exec_kpis
from src.service_layer.idea_service import create_idea, set_idea_status
from src.service_layer.s5_service import create_s5_audit
from src.service_layer.team_service import create_team
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.user_service import register_user
from src.config import IDEA_STATUS_IMPLEMENTED


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


def test_admin_sees_all_teams_kpis(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        _register_actor(uow, "m1@test.com", UserRole.EMPLOYEE.value, team_a)
        _register_actor(uow, "m2@test.com", UserRole.EMPLOYEE.value, team_a)
        _register_actor(uow, "m3@test.com", UserRole.EMPLOYEE.value, team_b)
        kpis = {k["team_id"]: k for k in list_exec_kpis(uow, admin)}
        assert set(kpis.keys()) == {team_a, team_b}
        assert kpis[team_a]["members"] == 2
        assert kpis[team_b]["members"] == 1


def test_manager_sees_only_own_team(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        manager_a = _register_actor(uow, "boss_a@test.com", UserRole.MANAGER.value, team_a)
        _register_actor(uow, "x@test.com", UserRole.EMPLOYEE.value, team_a)
        _register_actor(uow, "y@test.com", UserRole.EMPLOYEE.value, team_b)
        kpis = list_exec_kpis(uow, manager_a)
        assert [k["team_id"] for k in kpis] == [team_a]


def test_kpi_counts_combined(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        author = _register_actor(uow, "a@test.com", UserRole.EMPLOYEE.value, team_a)
        create_idea(uow, author, title="Melhoria", team_id=team_a)
        create_idea(uow, author, title="Implementada", team_id=team_a)
        ideas = list_exec_kpis(uow, admin)[0]
        assert ideas["open_ideas"] >= 2
        idea_ids = [i.idea_id for i in uow.users.list_ideas_by_team(team_a)]
        for iid in idea_ids:
                idea = uow.users.get_idea_by_id(iid)
                if idea.title == "Implementada":
                        set_idea_status(uow, admin, iid, IDEA_STATUS_IMPLEMENTED)
                        break
        kpis = {k["team_id"]: k for k in list_exec_kpis(uow, admin)}
        assert kpis[team_a]["implemented_ideas"] == 1


def test_accomplishment_and_kudos_counts(uow):
        from src.service_layer.culture_service import give_kudo
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        emp = _register_actor(uow, "e1@test.com", UserRole.EMPLOYEE.value, team_a)
        giver = _register_actor(uow, "g1@test.com", UserRole.EMPLOYEE.value, team_a)
        create_accomplishment(uow, admin, team_id=team_a, title="Meta atingida", start_date=date(2026, 1, 1))
        give_kudo(uow, giver, team_id=team_a, receiver_id=emp, message="Parabéns")
        kpis = {k["team_id"]: k for k in list_exec_kpis(uow, admin)}
        assert kpis[team_a]["accomplishments"] == 1
        assert kpis[team_a]["kudos"] == 1


def test_average_5s_included(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        create_s5_audit(uow, admin, team_id=team_a, date=date(2026, 1, 1), passed_ids=[0, 1, 2, 3, 4])
        kpis = {k["team_id"]: k for k in list_exec_kpis(uow, admin)}
        assert kpis[team_a]["avg_5s"] == 100.0


def test_period_filter_filters_accomplishments(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        create_accomplishment(uow, admin, team_id=team_a, title="Antiga", start_date=date(2025, 12, 1))
        create_accomplishment(uow, admin, team_id=team_a, title="Nova", start_date=date(2026, 2, 1))
        kpis = {k["team_id"]: k for k in list_exec_kpis(uow, admin, period_start=date(2026, 1, 1), period_end=date(2026, 2, 28))}
        assert kpis[team_a]["accomplishments"] == 1