from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.user_service import register_user, delete_user
from src.domain.model import AuditLog


def _setup():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    start_mappers()
    return SqlAlchemyUnitOfWork(session_factory)


def test_bulk_annotation_non_empty_details():
    uow = _setup()
    with uow:
        register_user(uow, "mgr@test.com", "pass", "manager")
        register_user(uow, "emp@test.com", "pass")
        m_id = uow.users.get_user_by_email("mgr@test.com").user_id
        e_id = uow.users.get_user_by_email("emp@test.com").user_id
        uow.session.add(AuditLog(user_id=e_id, action="X", target_id=None, timestamp=datetime.now(), details="some details"))
        uow.commit()
    delete_user(uow, m_id, e_id)
    with uow:
        logs = [l for l in uow.session.query(AuditLog).all() if l.user_id is None]
        assert any(l.details == "some details (User: emp@test.com)" for l in logs)


def test_bulk_annotation_null_details_becomes_prefix():
    uow = _setup()
    with uow:
        register_user(uow, "mgr2@test.com", "pass", "manager")
        register_user(uow, "emp2@test.com", "pass")
        m_id = uow.users.get_user_by_email("mgr2@test.com").user_id
        e_id = uow.users.get_user_by_email("emp2@test.com").user_id
        uow.session.add(AuditLog(user_id=e_id, action="X", target_id=None, timestamp=datetime.now(), details=None))
        uow.commit()
    delete_user(uow, m_id, e_id)
    with uow:
        logs = [l for l in uow.session.query(AuditLog).all() if l.user_id is None]
        assert any(l.details == "User: emp2@test.com" for l in logs)
