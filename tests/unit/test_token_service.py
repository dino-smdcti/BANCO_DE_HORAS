from src.service_layer import token_service
from src.domain.model import User, UserRole
from src.config import TOKEN_KIND_RESET, TOKEN_KIND_INVITE


def _create_user(uow, email):
    with uow:
        user = User(email=email, password_hash="!", role=UserRole.EMPLOYEE)
        uow.session.add(user)
        uow.commit()
        return user.user_id


class TestIssueAndConsume:
    def test_issue_and_consume_return_user_id(self, uow):
        uid = _create_user(uow, "t1@test.com")
        with uow:
            raw = token_service.issue_token(uow, uid, TOKEN_KIND_RESET, 300)
        with uow:
            assert token_service.consume_token(uow, raw, TOKEN_KIND_RESET) == uid

    def test_peek_does_not_consume(self, uow):
        uid = _create_user(uow, "t2@test.com")
        with uow:
            raw = token_service.issue_token(uow, uid, TOKEN_KIND_RESET, 300)
        with uow:
            assert token_service.peek_token(uow, raw, TOKEN_KIND_RESET) == uid
        with uow:
            assert token_service.peek_token(uow, raw, TOKEN_KIND_RESET) == uid

    def test_raw_token_is_not_stored(self, uow):
        uid = _create_user(uow, "t3@test.com")
        with uow:
            raw = token_service.issue_token(uow, uid, TOKEN_KIND_RESET, 300)
        with uow:
            token = uow.tokens.get_token_by_hash(token_service._hash(raw), TOKEN_KIND_RESET)
            token_hash = token.token_hash
        assert token is not None
        assert token_hash != raw

    def test_bogus_token_returns_none(self, uow):
        _create_user(uow, "t4@test.com")
        with uow:
            assert token_service.consume_token(uow, "not-a-real-token", TOKEN_KIND_RESET) is None

    def test_wrong_kind_returns_none(self, uow):
        uid = _create_user(uow, "t5@test.com")
        with uow:
            raw = token_service.issue_token(uow, uid, TOKEN_KIND_RESET, 300)
        with uow:
            assert token_service.consume_token(uow, raw, TOKEN_KIND_INVITE) is None


class TestSingleUse:
    def test_token_cannot_be_reused(self, uow):
        uid = _create_user(uow, "t6@test.com")
        with uow:
            raw = token_service.issue_token(uow, uid, TOKEN_KIND_RESET, 300)
        with uow:
            assert token_service.consume_token(uow, raw, TOKEN_KIND_RESET) == uid
        with uow:
            assert token_service.consume_token(uow, raw, TOKEN_KIND_RESET) is None
            assert token_service.peek_token(uow, raw, TOKEN_KIND_RESET) is None


class TestExpiry:
    def test_expired_token_rejected(self, uow):
        uid = _create_user(uow, "t7@test.com")
        with uow:
            raw = token_service.issue_token(uow, uid, TOKEN_KIND_RESET, -10)
        with uow:
            assert token_service.peek_token(uow, raw, TOKEN_KIND_RESET) is None
            assert token_service.consume_token(uow, raw, TOKEN_KIND_RESET) is None


class TestRevoke:
    def test_revoke_marks_outstanding_used(self, uow):
        uid = _create_user(uow, "t8@test.com")
        with uow:
            first = token_service.issue_token(uow, uid, TOKEN_KIND_RESET, 300)
            second = token_service.issue_token(uow, uid, TOKEN_KIND_RESET, 300)
        with uow:
            token_service.revoke_user_tokens(uow, uid, TOKEN_KIND_RESET)
        with uow:
            assert token_service.peek_token(uow, first, TOKEN_KIND_RESET) is None
            assert token_service.peek_token(uow, second, TOKEN_KIND_RESET) is None

    def test_revoke_scoped_to_kind(self, uow):
        uid = _create_user(uow, "t9@test.com")
        with uow:
            reset_raw = token_service.issue_token(uow, uid, TOKEN_KIND_RESET, 300)
            invite_raw = token_service.issue_token(uow, uid, TOKEN_KIND_INVITE, 300)
        with uow:
            token_service.revoke_user_tokens(uow, uid, TOKEN_KIND_RESET)
        with uow:
            assert token_service.peek_token(uow, reset_raw, TOKEN_KIND_RESET) is None
            assert token_service.peek_token(uow, invite_raw, TOKEN_KIND_INVITE) == uid
