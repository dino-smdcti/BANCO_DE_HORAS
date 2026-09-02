from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.user_service import register_user, delete_user
from src.domain.model import AuditLog, Team


def _setup():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    start_mappers()
    return SqlAlchemyUnitOfWork(session_factory)


def _make_team(uow):
    with uow:
        team = Team(name="audit")
        uow.session.add(team)
        uow.commit()
        return team.team_id


def _register_in_same_team(uow, mgr_email, emp_email):
    with uow:
        register_user(uow, mgr_email, "pass", "manager")
        register_user(uow, emp_email, "pass")
        m = uow.users.get_user_by_email(mgr_email)
        e = uow.users.get_user_by_email(emp_email)
        team_id = _make_team(uow)
        m.team_id = team_id
        e.team_id = team_id
        uow.commit()
        return m.user_id, e.user_id


def test_deactivate_keeps_row_and_flags_inactive():
    uow = _setup()
    with uow:
        m_id, e_id = _register_in_same_team(uow, "mgr@test.com", "emp@test.com")
        uow.session.add(AuditLog(user_id=e_id, action="X", target_id=None, timestamp=datetime.now(), details="some details"))
        uow.commit()
    delete_user(uow, m_id, e_id)
    with uow:
        employee = uow.users.get_user_by_id(e_id)
        assert employee is not None  # row kept (no hard delete / FK survives)
        assert employee.is_active is False


def test_deactivate_preserves_audit_user_reference():
    uow = _setup()
    with uow:
        m_id, e_id = _register_in_same_team(uow, "mgr2@test.com", "emp2@test.com")
        uow.session.add(AuditLog(user_id=e_id, action="X", target_id=None, timestamp=datetime.now(), details="some details"))
        uow.commit()
    delete_user(uow, m_id, e_id)
    with uow:
        logs = [l for l in uow.session.query(AuditLog).all() if l.user_id == e_id]
        assert len(logs) == 1  # user_id preserved for history/filter continuity