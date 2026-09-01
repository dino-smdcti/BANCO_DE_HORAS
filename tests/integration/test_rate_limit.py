import pytest
from unittest.mock import patch

from src.entrypoints.flask_app import app
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.config import RATE_LIMIT_MAX_ATTEMPTS


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


def _login_post(client, email="a@test.com", password="wrong"):
    return client.post("/login", data={"email": email, "password": password})


class TestRateLimit:
    def test_login_rejects_after_max_attempts(self, client, uow):
        for _ in range(RATE_LIMIT_MAX_ATTEMPTS):
            assert _login_post(client).status_code == 200
        throttled = _login_post(client)
        assert throttled.status_code == 429

    def test_forgot_password_shared_budget(self, client, uow):
        for _ in range(RATE_LIMIT_MAX_ATTEMPTS):
            assert _login_post(client).status_code == 200
        response = client.post("/forgot-password", data={"email": "nobody@test.com"})
        assert response.status_code == 429

    def test_magic_login_shared_budget(self, client, uow):
        for _ in range(RATE_LIMIT_MAX_ATTEMPTS):
            assert _login_post(client).status_code == 200
        response = client.post("/magic-login", data={"email": "nobody@test.com"})
        assert response.status_code == 429
