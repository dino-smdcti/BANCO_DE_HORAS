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


def _target_user(uow, uid):
    with uow:
        user = uow.users.get_user_by_id(uid)
        return user.role


class TestChangeUserRoleEscalation:
    def test_manager_cannot_change_any_role(self, client, uow):
        mgr = _create_user(uow, "mgr_esc@test.com", UserRole.MANAGER)
        target = _create_user(uow, "emp_esc@test.com", UserRole.EMPLOYEE)
        _login(client, mgr)
        r = client.post("/manager/change-role/%d" % target, json={"role": "admin"})
        assert r.status_code == 403
        assert _target_user(uow, target) == UserRole.EMPLOYEE

    def test_gestor_cannot_change_any_role(self, client, uow):
        gest = _create_user(uow, "gest_esc@test.com", UserRole.GESTOR)
        target = _create_user(uow, "emp_esc2@test.com", UserRole.EMPLOYEE)
        _login(client, gest)
        r = client.post("/manager/change-role/%d" % target, json={"role": "manager"})
        assert r.status_code == 403
        assert _target_user(uow, target) == UserRole.EMPLOYEE

    def test_admin_can_change_role(self, client, uow):
        adm = _create_user(uow, "adm_esc@test.com", UserRole.ADMIN)
        target = _create_user(uow, "emp_esc3@test.com", UserRole.EMPLOYEE)
        _login(client, adm)
        r = client.post("/manager/change-role/%d" % target, json={"role": "manager"})
        assert r.status_code == 200
        assert _target_user(uow, target) == UserRole.MANAGER

    def test_employee_cannot_change_any_role(self, client, uow):
        emp = _create_user(uow, "emp_esc4@test.com", UserRole.EMPLOYEE)
        target = _create_user(uow, "emp_esc5@test.com", UserRole.EMPLOYEE)
        _login(client, emp)
        r = client.post("/manager/change-role/%d" % target, json={"role": "admin"})
        assert r.status_code == 403
        assert _target_user(uow, target) == UserRole.EMPLOYEE

    def test_invalid_role_rejected(self, client, uow):
        adm = _create_user(uow, "adm_esc6@test.com", UserRole.ADMIN)
        target = _create_user(uow, "emp_esc7@test.com", UserRole.EMPLOYEE)
        _login(client, adm)
        r = client.post("/manager/change-role/%d" % target, json={"role": "root"})
        assert r.status_code == 400
        assert _target_user(uow, target) == UserRole.EMPLOYEE
