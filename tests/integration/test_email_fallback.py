import pytest
from unittest.mock import patch

from src.entrypoints.flask_app import app
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.domain.model import User, UserRole
from werkzeug.security import generate_password_hash


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


def _create_user(uow, email, role):
    with uow:
        user = User(email=email, password_hash=generate_password_hash("pass"), role=role)
        uow.session.add(user)
        uow.commit()
        return user.user_id


def _login(client, uid):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)


class TestEmailFallback:
    def test_manager_sees_fallback_when_email_fails(self, client, uow):
        mgr = _create_user(uow, "mgr_fb@test.com", UserRole.MANAGER)
        target = _create_user(uow, "emp_fb@test.com", UserRole.EMPLOYEE)
        _login(client, mgr)
        with patch("src.entrypoints.flask_app.send_email", return_value=False):
            r = client.post("/manager/reset-user-password/%d" % target)
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        assert "E-mail não pôde ser entregue" in body
        assert "/reset-password/" in body

    def test_manager_sees_fallback_on_invite(self, client, uow):
        mgr = _create_user(uow, "mgr_fb3@test.com", UserRole.MANAGER)
        _login(client, mgr)
        with patch("src.entrypoints.flask_app.send_email", return_value=False):
            r = client.post("/register", data={"email": "newbie@test.com", "role": "employee"})
        assert r.status_code == 200
        assert "E-mail não pôde ser entregue" in r.get_data(as_text=True)

    def test_employee_never_receives_fallback_page(self, client, uow):
        emp = _create_user(uow, "emp_fb4@test.com", UserRole.EMPLOYEE)
        target = _create_user(uow, "emp_fb5@test.com", UserRole.EMPLOYEE)
        _login(client, emp)
        with patch("src.entrypoints.flask_app.send_email", return_value=False):
            r = client.post("/manager/reset-user-password/%d" % target, follow_redirects=False)
        # Employee is role-guarded away from the manager route: no fallback page.
        assert r.status_code == 302
