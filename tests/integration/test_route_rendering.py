import pytest
from unittest.mock import patch
from datetime import time, date
from src.entrypoints.flask_app import app
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer import services
from src.domain.model import User, JourneyType
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client(session_factory):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    # Prevent before_request absence processor from interfering with tests
    patcher = patch("src.entrypoints.flask_app.process_daily_absences", lambda uow: None)
    patcher.start()

    with patch("src.entrypoints.flask_app.SqlAlchemyUnitOfWork", lambda: SqlAlchemyUnitOfWork(session_factory)):
        with app.test_client() as c:
            yield c

    patcher.stop()


@pytest.fixture
def db(uow):
    """Provide raw uow access and ensure cleanup."""
    yield uow


# ---------------------------------------------------------------------------
# Helper: create user directly in DB
# ---------------------------------------------------------------------------

def _create_user(uow, email, role="employee", password="pass",
                 complete_profile=False, with_schedule=False):
    with uow:
        user = User(email=email, password_hash=generate_password_hash(password), role=role)
        uow.session.add(user)
        uow.commit()
        uid = user.user_id

        if complete_profile:
            services.update_user_profile(
                uow, uid, "", "", "IT", "Dev", "SMDCTI", "Test User"
            )

        if with_schedule:
            services.set_work_schedule(
                uow, uid, uid,
                time(8, 0), time(12, 0), time(13, 0), time(17, 0)
            )
            uow.commit()

        return uid


def _login(client, uid):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)


def _create_journey(uow, name="Jornada Teste"):
    with uow:
        jt = JourneyType(
            name=name,
            expected_arrival=time(8, 0),
            expected_lunch_start=time(12, 0),
            expected_lunch_end=time(13, 0),
            expected_departure=time(17, 0),
            tolerance_minutes=15,
        )
        uow.session.add(jt)
        uow.commit()
        return jt.journey_id


# ===================================================================
# 1. PUBLIC ROUTES  (no authentication required)
# ===================================================================

class TestPublicRoutes:
    def test_index(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_login_page(self, client):
        r = client.get("/login")
        assert r.status_code == 200

    def test_forgot_password_page(self, client):
        r = client.get("/forgot-password")
        assert r.status_code == 200

    def test_favicon(self, client):
        r = client.get("/favicon.ico")
        assert r.status_code == 200


# ===================================================================
# 2. PROTECTED ROUTES – UNAUTHENTICATED  (should redirect to login)
# ===================================================================

class TestProtectedRoutesUnauthenticated:
    def test_dashboard_redirects(self, client):
        r = client.get("/dashboard", follow_redirects=False)
        assert r.status_code == 302

    def test_profile_redirects(self, client):
        r = client.get("/profile", follow_redirects=False)
        assert r.status_code == 302

    def test_choose_journey_redirects(self, client):
        r = client.get("/choose-journey", follow_redirects=False)
        assert r.status_code == 302

    def test_complete_profile_redirects(self, client):
        r = client.get("/complete-profile", follow_redirects=False)
        assert r.status_code == 302

    def test_register_redirects(self, client):
        r = client.get("/register", follow_redirects=False)
        assert r.status_code == 302

    def test_management_redirects(self, client):
        r = client.get("/management", follow_redirects=False)
        assert r.status_code == 302


# ===================================================================
# 3. EMPLOYEE ROUTES  (authenticated as employee)
# ===================================================================

class TestEmployeeRoutes:
    def test_dashboard_employee(self, client, uow):
        uid = _create_user(uow, "emp_dash@test.com", complete_profile=True, with_schedule=True)
        _login(client, uid)
        r = client.get("/dashboard", follow_redirects=False)
        if r.status_code != 200:
            print(f"DASHBOARD REDIRECT: {r.status_code} -> {r.headers.get('Location')}")
            # Check if has_schedule is True
            with client.session_transaction() as sess:
                from flask_login import current_user
                print(f"current_user id: {sess.get('_user_id')}")
        assert r.status_code == 200

    def test_dashboard_redirects_to_complete_profile(self, client, uow):
        uid = _create_user(uow, "emp_noprofile@test.com")
        _login(client, uid)
        r = client.get("/dashboard", follow_redirects=False)
        assert r.status_code == 302

    def test_dashboard_redirects_to_choose_journey(self, client, uow):
        uid = _create_user(uow, "emp_nosched@test.com", complete_profile=True)
        _login(client, uid)
        r = client.get("/dashboard", follow_redirects=False)
        assert r.status_code == 302

    def test_profile_page(self, client, uow):
        uid = _create_user(uow, "emp_prof@test.com")
        _login(client, uid)
        r = client.get("/profile")
        assert r.status_code == 200

    def test_complete_profile_renders(self, client, uow):
        uid = _create_user(uow, "emp_cp@test.com")
        _login(client, uid)
        r = client.get("/complete-profile")
        assert r.status_code == 200

    def test_choose_journey_renders(self, client, uow):
        _create_journey(uow)
        uid = _create_user(uow, "emp_cj@test.com", complete_profile=True)
        _login(client, uid)
        r = client.get("/choose-journey")
        assert r.status_code == 200
        assert b"Jornada Teste" in r.data


# ===================================================================
# 4. MANAGER ROUTES  (authenticated as manager)
# ===================================================================

class TestManagerRoutes:
    def test_register_page(self, client, uow):
        uid = _create_user(uow, "mgr_reg@test.com", role="manager")
        _login(client, uid)
        r = client.get("/register")
        assert r.status_code == 200

    def test_management_panel(self, client, uow):
        uid = _create_user(uow, "mgr_mgmt@test.com", role="manager")
        _login(client, uid)
        r = client.get("/management")
        assert r.status_code == 200

    def test_journey_types_page(self, client, uow):
        _create_journey(uow)
        uid = _create_user(uow, "mgr_jt@test.com", role="manager")
        _login(client, uid)
        r = client.get("/manager/journey-types")
        assert r.status_code == 200
        assert b"Jornada Teste" in r.data

    def test_edit_journey_page(self, client, uow):
        jid = _create_journey(uow)
        uid = _create_user(uow, "mgr_editj@test.com", role="manager")
        _login(client, uid)
        r = client.get(f"/manager/edit-journey/{jid}")
        assert r.status_code == 200
        assert b"Jornada Teste" in r.data

    def test_get_journey_json(self, client, uow):
        jid = _create_journey(uow)
        uid = _create_user(uow, "mgr_getj@test.com", role="manager")
        _login(client, uid)
        r = client.get(f"/manager/get-journey/{jid}")
        assert r.status_code == 200
        assert r.is_json
        data = r.get_json()
        assert data["arrival"] == "08:00"
        assert data["departure"] == "17:00"

    def test_set_schedule_page(self, client, uow):
        _create_journey(uow)
        mgr_id = _create_user(uow, "mgr_ss@test.com", role="manager")
        emp_id = _create_user(uow, "emp_ss@test.com")
        _login(client, mgr_id)
        r = client.get(f"/manager/set-schedule/{emp_id}")
        assert r.status_code == 200

    def test_view_employee_logs(self, client, uow):
        mgr_id = _create_user(uow, "mgr_logs@test.com", role="manager")
        emp_id = _create_user(uow, "emp_logs@test.com")
        _login(client, mgr_id)
        r = client.get(f"/manager/view-logs/{emp_id}")
        assert r.status_code == 200

    def test_fix_ponto_page(self, client, uow):
        mgr_id = _create_user(uow, "mgr_fix@test.com", role="manager")
        emp_id = _create_user(uow, "emp_fix@test.com")
        _login(client, mgr_id)
        r = client.get(f"/manager/fix-ponto/{emp_id}")
        assert r.status_code == 200

    def test_edit_employee_page(self, client, uow):
        mgr_id = _create_user(uow, "mgr_ee@test.com", role="manager")
        emp_id = _create_user(uow, "emp_ee@test.com", complete_profile=True)
        _login(client, mgr_id)
        r = client.get(f"/manager/edit-employee/{emp_id}")
        assert r.status_code == 200

    def test_archived_justifications(self, client, uow):
        mgr_id = _create_user(uow, "mgr_aj@test.com", role="manager")
        _login(client, mgr_id)
        r = client.get("/manager/archived-justifications")
        assert r.status_code == 200


# ===================================================================
# 5. ADMIN / GESTOR ROUTES
# ===================================================================

class TestAdminRoutes:
    def test_admin_settings(self, client, uow):
        uid = _create_user(uow, "adm_set@test.com", role="admin")
        _login(client, uid)
        r = client.get("/admin/settings")
        assert r.status_code == 200

    def test_audit_logs(self, client, uow):
        uid = _create_user(uow, "adm_audit@test.com", role="admin")
        _login(client, uid)
        r = client.get("/admin/audit-logs")
        assert r.status_code == 200

    def test_gestor_can_access_settings(self, client, uow):
        uid = _create_user(uow, "gest_set@test.com", role="gestor")
        _login(client, uid)
        r = client.get("/admin/settings")
        assert r.status_code == 200


# ===================================================================
# 6. ROLE-BASED ACCESS CONTROL  (employee accessing manager routes)
# ===================================================================

class TestAccessControl:
    def test_employee_cannot_access_management(self, client, uow):
        uid = _create_user(uow, "emp_nomgmt@test.com")
        _login(client, uid)
        r = client.get("/management", follow_redirects=False)
        assert r.status_code == 302

    def test_employee_cannot_access_journey_types(self, client, uow):
        uid = _create_user(uow, "emp_nojt@test.com")
        _login(client, uid)
        r = client.get("/manager/journey-types", follow_redirects=False)
        assert r.status_code == 302

    def test_employee_cannot_access_admin_settings(self, client, uow):
        uid = _create_user(uow, "emp_noadm@test.com")
        _login(client, uid)
        r = client.get("/admin/settings", follow_redirects=False)
        assert r.status_code == 302

    def test_employee_cannot_access_register(self, client, uow):
        uid = _create_user(uow, "emp_noreg@test.com")
        _login(client, uid)
        r = client.get("/register", follow_redirects=False)
        assert r.status_code == 302


# ===================================================================
# 7. PASSWORD RESET FLOW
# ===================================================================

class TestPasswordReset:
    def test_reset_password_page_invalid_token(self, client):
        r = client.get("/reset-password/invalid-token", follow_redirects=True)
        assert r.status_code == 200

    def test_reset_password_page_valid_token(self, client, uow):
        from src.entrypoints.flask_app import serializer
        services.register_user(uow, "reset@test.com", "oldpass")
        token = serializer.dumps("reset@test.com", salt="password-reset-salt")
        r = client.get(f"/reset-password/{token}")
        assert r.status_code == 200
