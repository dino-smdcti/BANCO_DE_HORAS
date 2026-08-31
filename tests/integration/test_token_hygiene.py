import pytest
from unittest.mock import patch

from src.entrypoints.flask_app import app, serializer, _resolve_secret_key
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.domain.model import User, UserRole
from src.config import TOKEN_SALT_INVITE, TOKEN_SALT_PASSWORD_RESET


@pytest.fixture
def client(session_factory):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    patcher = patch("src.entrypoints.flask_app.process_daily_absences", lambda uow: None)
    patcher.start()
    with patch("src.entrypoints.flask_app.SqlAlchemyUnitOfWork", lambda: SqlAlchemyUnitOfWork(session_factory)):
        with app.test_client() as c:
            yield c
    patcher.stop()


def _create_user(uow, email):
    with uow:
        user = User(email=email, password_hash="!", role=UserRole.EMPLOYEE)
        uow.session.add(user)
        uow.commit()
        return user.user_id


class TestDistinctInviteSalt:
    def test_invite_token_works_on_invite_route(self, client, uow):
        uid = _create_user(uow, "salt_inv@test.com")
        token = serializer.dumps("salt_inv@test.com", salt=TOKEN_SALT_INVITE)
        r = client.get("/invite/%s" % token)
        assert r.status_code == 200

    def test_invite_token_rejected_on_reset_route(self, client, uow):
        uid = _create_user(uow, "salt_inv2@test.com")
        token = serializer.dumps("salt_inv2@test.com", salt=TOKEN_SALT_INVITE)
        r = client.get("/reset-password/%s" % token, follow_redirects=False)
        assert r.status_code == 302

    def test_reset_token_rejected_on_invite_route(self, client, uow):
        uid = _create_user(uow, "salt_inv3@test.com")
        token = serializer.dumps("salt_inv3@test.com", salt=TOKEN_SALT_PASSWORD_RESET)
        r = client.get("/invite/%s" % token, follow_redirects=False)
        assert r.status_code == 302

    def test_reset_token_works_on_reset_route(self, client, uow):
        uid = _create_user(uow, "salt_inv4@test.com")
        token = serializer.dumps("salt_inv4@test.com", salt=TOKEN_SALT_PASSWORD_RESET)
        r = client.get("/reset-password/%s" % token)
        assert r.status_code == 200

    def test_invite_token_cannot_reset_password(self, client, uow):
        uid = _create_user(uow, "salt_inv5@test.com")
        token = serializer.dumps("salt_inv5@test.com", salt=TOKEN_SALT_INVITE)
        r = client.post(
            "/reset-password/%s" % token,
            data={"password": "newsecret123"},
            follow_redirects=False,
        )
        assert r.status_code == 302


class TestSecretKeyProductionGate:
    def test_missing_raises_in_production(self):
        with pytest.raises(RuntimeError):
            _resolve_secret_key({"FLASK_ENV": "production"})

    def test_missing_raises_on_vercel(self):
        with pytest.raises(RuntimeError):
            _resolve_secret_key({"VERCEL": "1"})

    def test_present_used_in_production(self):
        assert _resolve_secret_key({"FLASK_ENV": "production", "SECRET_KEY": "s3cret"}) == "s3cret"

    def test_dev_falls_back_when_unset(self):
        assert _resolve_secret_key({}) == "dev-only-insecure-secret-key"

    def test_dev_uses_explicit_value(self):
        assert _resolve_secret_key({"SECRET_KEY": "local-key"}) == "local-key"
