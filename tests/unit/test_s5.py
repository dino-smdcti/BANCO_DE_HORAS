from datetime import date

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.domain.model import UserRole
from src.service_layer.s5_service import (
        DEFAULT_S5_ITEMS,
        create_s5_audit,
        delete_s5_audit,
        get_s5_average,
        list_s5_audits,
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


def test_create_s5_audit_computes_score(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        create_s5_audit(uow, admin, team_id=team_a, date=date(2026, 1, 15))
        audits = list_s5_audits(uow, admin, team_id=team_a)
        assert len(audits) == 1
        assert audits[0].score == 0.0
        assert len(audits[0].items) == len(DEFAULT_S5_ITEMS)
        assert all(not i.passed for i in audits[0].items)


def test_create_s5_audit_partial_passed_score(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        create_s5_audit(uow, admin, team_id=team_a, date=date(2026, 2, 1), passed_ids=[0, 1, 2])
        audits = list_s5_audits(uow, admin, team_id=team_a)
        assert audits[0].score == 60.0


def test_create_s5_audit_denied_out_of_scope(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        manager_a = _register_actor(uow, "mgr5@test.com", UserRole.MANAGER.value, team_a)
        with pytest.raises(PermissionError):
                create_s5_audit(uow, manager_a, team_id=team_b, date=date(2026, 1, 1))


def test_list_s5_audits_scoped_by_team(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        create_s5_audit(uow, admin, team_id=team_a, date=date(2026, 1, 1))
        create_s5_audit(uow, admin, team_id=team_b, date=date(2026, 1, 2))
        manager_a = _register_actor(uow, "mgr6@test.com", UserRole.MANAGER.value, team_a)
        titles = [a.team_id for a in list_s5_audits(uow, manager_a)]
        assert titles == [team_a]


def test_average_s5_score(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        create_s5_audit(uow, admin, team_id=team_a, date=date(2026, 1, 1), passed_ids=[0, 1, 2, 3, 4])
        create_s5_audit(uow, admin, team_id=team_a, date=date(2026, 2, 1), passed_ids=[0, 1])
        assert get_s5_average(uow, admin, team_a) == 70.0


def test_get_s5_average_denied_out_of_scope(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        create_s5_audit(uow, admin, team_id=team_a, date=date(2026, 1, 1))
        manager_b = _register_actor(uow, "mgr7@test.com", UserRole.MANAGER.value, team_b)
        with pytest.raises(PermissionError):
                get_s5_average(uow, manager_b, team_a)


def test_delete_s5_audit_manager_only(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        employee = _register_actor(uow, "emp5@test.com", UserRole.EMPLOYEE.value, team_a)
        create_s5_audit(uow, admin, team_id=team_a, date=date(2026, 1, 1))
        audits = list_s5_audits(uow, admin, team_id=team_a)
        audit_id = audits[0].s5_audit_id
        with pytest.raises(PermissionError):
                delete_s5_audit(uow, employee, audit_id)
        delete_s5_audit(uow, admin, audit_id)
        assert list_s5_audits(uow, admin, team_id=team_a) == []