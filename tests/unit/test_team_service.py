import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.service_layer import services
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.user_service import register_user


def _session_uow():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    start_mappers()
    return SqlAlchemyUnitOfWork(session_factory)


def _register(uow, email, role):
    with uow:
        register_user(uow, email, "pass", role)
        return uow.users.get_user_by_email(email).user_id


def _created_team_id(uow, actor, name, secretariat=None):
    with uow:
        team = services.create_team(uow, actor, name, secretariat)
        return team.team_id


def test_create_team_requires_admin_or_gestor():
    for role in ("admin", "gestor"):
        uow = _session_uow()
        actor = _register(uow, f"actor_{role}@test.com", role)
        team_id = _created_team_id(uow, actor, "Equipe TI")
        with uow:
            assert uow.users.get_team_by_id(team_id).name == "Equipe TI"
    for role in ("manager", "employee"):
        uow = _session_uow()
        actor = _register(uow, f"denied_{role}@test.com", role)
        with pytest.raises(PermissionError):
            services.create_team(uow, actor, "Equipe TI")


def test_create_team_rejects_duplicate_and_blank_names():
    uow = _session_uow()
    admin = _register(uow, "adm_dup@test.com", "admin")
    services.create_team(uow, admin, "Equipe A")
    with pytest.raises(ValueError):
        services.create_team(uow, admin, "Equipe A")
    with pytest.raises(ValueError):
        services.create_team(uow, admin, "   ")


def test_assign_user_team_updates_and_unassigns():
    uow = _session_uow()
    admin = _register(uow, "adm_assign@test.com", "admin")
    emp = _register(uow, "emp_assign@test.com", "employee")
    team_id = _created_team_id(uow, admin, "Equipe X")

    services.assign_user_team(uow, admin, emp, team_id)
    with uow:
        assert uow.users.get_user_by_id(emp).team_id == team_id

    services.assign_user_team(uow, admin, emp, None)
    with uow:
        assert uow.users.get_user_by_id(emp).team_id is None


def test_assign_user_team_validates_targets():
    uow = _session_uow()
    admin = _register(uow, "adm_validate@test.com", "admin")
    emp = _register(uow, "emp_validate@test.com", "employee")
    with pytest.raises(ValueError):
        services.assign_user_team(uow, admin, emp, 9999)
    with pytest.raises(ValueError):
        services.assign_user_team(uow, admin, 9999, None)


def test_assign_user_team_requires_admin_or_gestor():
    uow = _session_uow()
    mgr = _register(uow, "mgr_assign@test.com", "manager")
    emp = _register(uow, "emp_assign2@test.com", "employee")
    admin = _register(uow, "adm_tmp@test.com", "admin")
    team_id = _created_team_id(uow, admin, "Equipe Y")
    with pytest.raises(PermissionError):
        services.assign_user_team(uow, mgr, emp, team_id)


def test_list_teams_and_members():
    uow = _session_uow()
    admin = _register(uow, "adm_list@test.com", "admin")
    emp = _register(uow, "emp_list@test.com", "employee")
    team_id = _created_team_id(uow, admin, "Equipe Z", secretariat="SMDCTI")
    with uow:
        assert [t.name for t in services.list_teams(uow)] == ["Equipe Z"]
    services.assign_user_team(uow, admin, emp, team_id)
    with uow:
        assert [m.user_id for m in services.list_team_members(uow, team_id)] == [emp]