import pytest
from unittest.mock import patch

from src.entrypoints.flask_app import app
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture
def client(session_factory):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    patcher = patch("src.entrypoints.flask_app.process_daily_absences", lambda uow: None)
    patcher.start()
    try:
        with patch("src.entrypoints.flask_app.SqlAlchemyUnitOfWork",
                   lambda: SqlAlchemyUnitOfWork(session_factory)):
            with app.test_client() as c:
                yield c
    finally:
        patcher.stop()


def _make_user(uow, email):
    from src.domain.model import User
    from werkzeug.security import generate_password_hash
    with uow:
        user = User(email=email, password_hash=generate_password_hash("pass"), role="employee", password_set=True)
        uow.session.add(user)
        uow.commit()
        return user.user_id


def test_logout_get_rejected(client, uow):
    uid = _make_user(uow, "who@test.com")
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
    response = client.get("/logout")
    assert response.status_code == 405


def test_logout_post_clears_session(client, uow):
    uid = _make_user(uow, "who2@test.com")
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
    response = client.post("/logout")
    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert "_user_id" not in sess
