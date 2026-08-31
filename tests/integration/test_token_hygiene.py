import pytest
from unittest.mock import patch

from src.entrypoints.flask_app import app, _resolve_secret_key
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer import token_service
from src.domain.model import User, UserRole
from src.config import TOKEN_KIND_INVITE, TOKEN_KIND_RESET


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


class TestKindSeparation:
    def test_invite_token_works_on_invite_route(self, client, uow):
        uid = _create_user(uow, "salt_inv@test.com")
        with uow:
            raw = token_service.issue_token(uow, uid, TOKEN_KIND_INVITE, 300)
        r = client.get("/invite/%s" % raw)
        assert r.status_code == 200

    def test_invite_token_rejected_on_reset_route(self, client, uow):
        uid = _create_user(uow, "salt_inv2@test.com")
        with uow:
            raw = token_service.issue_token(uow, uid, TOKEN_KIND_INVITE, 300)
        r = client.get("/reset-password/%s" % raw, follow_redirects=False)
        assert r.status_code == 302

    def test_reset_token_rejected_on_invite_route(self, client, uow):
        uid = _create_user(uow, "salt_inv3@test.com")
        with uow:
            raw = token_service.issue_token(uow, uid, TOKEN_KIND_RESET, 300)
        r = client.get("/invite/%s" % raw, follow_redirects=False)
        assert r.status_code == 302

    def test_reset_token_works_on_reset_route(self, client, uow):
        uid = _create_user(uow, "salt_inv4@test.com")
        with uow:
            raw = token_service.issue_token(uow, uid, TOKEN_KIND_RESET, 300)
        r = client.get("/reset-password/%s" % raw)
        assert r.status_code == 200

    def test_invite_token_cannot_reset_password(self, client, uow):
        uid = _create_user(uow, "salt_inv5@test.com")
        with uow:
            raw = token_service.issue_token(uow, uid, TOKEN_KIND_INVITE, 300)
        r = client.post(
            "/reset-password/%s" % raw,
            data={"password": "newsecret123"},
            follow_redirects=False,
        )
        assert r.status_code == 302


class TestSingleUse:
    def test_reset_token_consumed_after_use(self, client, uow):
        uid = _create_user(uow, "single_use@test.com")
        with uow:
            raw = token_service.issue_token(uow, uid, TOKEN_KIND_RESET, 300)
        r = client.post(
            "/reset-password/%s" % raw,
            data={"password": "newsecret123"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        with uow:
            still_valid = token_service.peek_token(uow, raw, TOKEN_KIND_RESET)
        assert still_valid is None

    def test_reused_reset_token_rejected(self, client, uow):
        uid = _create_user(uow, "reuse@test.com")
        with uow:
            raw = token_service.issue_token(uow, uid, TOKEN_KIND_RESET, 300)
        client.post("/reset-password/%s" % raw, data={"password": "pass12345"}, follow_redirects=False)
        r = client.post(
            "/reset-password/%s" % raw,
            data={"password": "otherpass123"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        with uow:
            user = uow.users.get_user_by_id(uid)
            stored_hash = user.password_hash
        from werkzeug.security import check_password_hash
        assert check_password_hash(stored_hash, "pass12345")
        assert not check_password_hash(stored_hash, "otherpass123")

    def test_invite_token_single_use(self, client, uow):
        uid = _create_user(uow, "inv_single@test.com")
        with uow:
            raw = token_service.issue_token(uow, uid, TOKEN_KIND_INVITE, 300)
        r = client.post(
            "/invite/%s" % raw,
            data={"password": "setpass123"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        with uow:
            still_valid = token_service.peek_token(uow, raw, TOKEN_KIND_INVITE)
        assert still_valid is None


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
