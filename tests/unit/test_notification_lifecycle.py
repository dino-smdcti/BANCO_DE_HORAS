from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.service_layer import services
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.user_service import register_user


def _session_uow():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    start_mappers()
    return SqlAlchemyUnitOfWork(session_factory)


def _register(uow, email):
    with uow:
        register_user(uow, email, "pass", "employee")
        return uow.users.get_user_by_email(email).user_id


def test_add_notification_then_mark_read_toggles_unread_count():
    uow = _session_uow()
    uid = _register(uow, "notif@test.com")
    services.add_notification(uow, uid, "Primeira")
    services.add_notification(uow, uid, "Segunda")
    with uow:
        user = uow.users.get_user_by_id(uid)
        assert user.unread_notifications_count == 2
        assert [n.is_read for n in user.notifications] == [False, False]

    services.mark_notifications_as_read(uow, uid)
    with uow:
        user = uow.users.get_user_by_id(uid)
        assert user.unread_notifications_count == 0
        assert all(n.is_read for n in user.notifications)
        assert [n.message for n in user.notifications] == ["Segunda", "Primeira"]


def test_mark_read_is_identity_for_unknown_user():
    uow = _session_uow()
    services.mark_notifications_as_read(uow, 9999)


def test_email_sent_only_when_opted_in():
    uow = _session_uow()
    uid = _register(uow, "notif_opt@test.com")
    sent = []
    with uow:
        uow.users.get_user_by_id(uid).email_notifications_enabled = True
        uow.commit()
    services.add_notification(uow, uid, "Com email", email_sender=lambda to, subj, body: sent.append(to))
    with uow:
        target = uow.users.get_user_by_id(uid)
        assert target.email_notifications_enabled is True
    assert sent == ["notif_opt@test.com"]

    uow2 = _session_uow()
    uid2 = _register(uow2, "notif_no_opt@test.com")
    services.add_notification(uow2, uid2, "Sem email", email_sender=lambda to, subj, body: sent.append(to))
    assert sent == ["notif_opt@test.com"]
    with uow2:
        assert uow2.users.get_user_by_id(uid2).unread_notifications_count == 1