import pytest

from src.service_layer.user_service import register_user, update_credentials
from src.domain.model import User, UserRole
from werkzeug.security import check_password_hash


class TestPasswordSet:
    def test_user_defaults_password_set_from_hash(self):
        assert User(email="a@t.com", password_hash="!", role=UserRole.EMPLOYEE).password_set is False
        assert User(email="a@t.com", password_hash="x", role=UserRole.EMPLOYEE).password_set is True
        assert User(email="a@t.com", password_hash="x", role=UserRole.EMPLOYEE, password_set=False).password_set is False

    def test_register_without_password_marks_not_set(self, uow):
        register_user(uow, "nopass@test.com")
        with uow:
            user = uow.users.get_user_by_email("nopass@test.com")
            assert user.password_set is False
            assert user.password_hash == "_unset_password_"

    def test_register_with_password_marks_set(self, uow):
        register_user(uow, "withpass@test.com", "secret123")
        with uow:
            user = uow.users.get_user_by_email("withpass@test.com")
            assert user.password_set is True
            assert check_password_hash(user.password_hash, "secret123")

    def test_passwordless_hash_never_matches(self, uow):
        register_user(uow, "nopass2@test.com")
        with uow:
            user = uow.users.get_user_by_email("nopass2@test.com")
            assert not check_password_hash(user.password_hash, "anything")

    def test_update_credentials_sets_password_set(self, uow):
        register_user(uow, "up@test.com")
        with uow:
            uid = uow.users.get_user_by_email("up@test.com").user_id
        update_credentials(uow, uid, "up@test.com", password="newpass123")
        with uow:
            user = uow.users.get_user_by_email("up@test.com")
            assert user.password_set is True
            assert check_password_hash(user.password_hash, "newpass123")
