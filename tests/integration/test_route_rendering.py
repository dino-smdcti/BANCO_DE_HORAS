import pytest
from unittest.mock import patch
from datetime import time, date
from src.entrypoints.flask_app import app
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer import services
from src.domain.model import User, JourneyType, DailyPonto, PontoStatus
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


# ===================================================================
# 8. ABSENCES CARD  (only MISSING + manager-note logs, dismiss/delete)
# ===================================================================

def _add_ponto(uow, user_id, entry_date, status=PontoStatus.MISSING, manager_notes=None, notes=None):
    with uow:
        user = uow.users.get_user_by_id(user_id)
        ponto = DailyPonto(
            user_id=user_id,
            entry_date=entry_date,
            status=status,
            manager_notes=manager_notes,
            notes=notes,
        )
        user.time_entries.append(ponto)
        uow.commit()
        return user_id


def _create_manager(uow):
    return _create_user(uow, "mgr_card@test.com", role="manager")


class TestAbsencesCard:
    def test_card_only_shows_missing_and_user_notes(self, client, uow):
        mgr = _create_manager(uow)
        emp = _create_user(uow, "emp_card@test.com", complete_profile=True, with_schedule=True)
        _add_ponto(uow, emp, date(2026, 5, 4), status=PontoStatus.MISSING)
        _add_ponto(uow, emp, date(2026, 5, 5), status=PontoStatus.LATE, notes="sem nota")
        _add_ponto(uow, emp, date(2026, 5, 6), status=PontoStatus.ON_TIME, manager_notes="Atestado")
        _add_ponto(uow, emp, date(2026, 5, 7), status=PontoStatus.DISMISSED)
        _add_ponto(uow, emp, date(2026, 5, 8), status=PontoStatus.CORRECTED)
        _login(client, mgr)
        body = client.get("/management").data.decode("utf-8")
        assert "04/05/2026" in body
        assert "05/05/2026" in body
        assert "sem nota" in body
        assert "06/05/2026" not in body
        assert "07/05/2026" not in body
        assert "08/05/2026" not in body

    def test_archive_dismisses_note_entry(self, client, uow):
        mgr = _create_manager(uow)
        emp = _create_user(uow, "emp_arch@test.com", complete_profile=True, with_schedule=True)
        _add_ponto(uow, emp, date(2026, 5, 10), status=PontoStatus.MISSING, notes="Atestado Influenza")
        _login(client, mgr)
        client.post(f"/manager/archive-justification/{emp}/{date(2026, 5, 10)}")
        body = client.get("/management").data.decode("utf-8")
        assert "10/05/2026" not in body

    def test_delete_removes_entry(self, client, uow):
        mgr = _create_manager(uow)
        emp = _create_user(uow, "emp_del@test.com", complete_profile=True, with_schedule=True)
        _add_ponto(uow, emp, date(2026, 5, 12), status=PontoStatus.MISSING)
        _login(client, mgr)
        client.post(f"/manager/delete-ponto/{emp}/{date(2026, 5, 12)}")
        body = client.get("/management").data.decode("utf-8")
        assert "12/05/2026" not in body


# ===================================================================
# 9. AUDIT LOGS PAGE
# ===================================================================

class TestAuditLogsPage:
    def test_audit_logs_show_rows_without_filters(self, client, uow):
        admin = _create_user(uow, "adm_audit@test.com", role="admin")
        with uow:
            uow.record_action(admin, "DELETE_PONTO", target_id=1, details="Registro de auditoria de teste")
            uow.commit()
        _login(client, admin)
        r = client.get("/admin/audit-logs")
        assert r.status_code == 200
        body = r.data.decode("utf-8")
        assert "Registro de auditoria de teste" in body
        assert "Utilize os filtros" not in body

    def test_audit_logs_actor_filter_present(self, client, uow):
        admin = _create_user(uow, "adm_audit2@test.com", role="admin")
        _login(client, admin)
        r = client.get("/admin/audit-logs")
        assert r.status_code == 200
        assert b"actor_search" in r.data


# ===================================================================
# 10. ATTESTATION (LANÇAR ATESTADO) & FACULTATIVO
# ===================================================================

class TestAttestation:
    def test_full_day_attestation_keeps_dismissed_log(self, client, uow):
        mgr = _create_manager(uow)
        emp = _create_user(uow, "emp_att_full@test.com", complete_profile=True, with_schedule=True)
        _add_ponto(uow, emp, date(2026, 5, 15), status=PontoStatus.MISSING)
        _login(client, mgr)
        r = client.post(
            f"/manager/add-attestation/{emp}",
            data={"start_date": "2026-05-15", "end_date": "2026-05-15", "cid": "J06"},
        )
        assert r.status_code == 302
        with uow:
            user = uow.users.get_user_by_id(emp)
            ponto = next(p for p in user.time_entries if p.entry_date == date(2026, 5, 15))
            assert ponto.status == PontoStatus.DISMISSED
            assert ponto.excused_minutes == 0
            assert ponto.manager_notes and "J06" in ponto.manager_notes
            assert user.is_on_attestation(date(2026, 5, 15))
            assert not user.is_on_attestation(date(2026, 5, 16))

    def test_partial_attestation_credits_missed_minutes(self, client, uow):
        mgr = _create_manager(uow)
        emp = _create_user(uow, "emp_att_part@test.com", complete_profile=True, with_schedule=True)
        with uow:
            user = uow.users.get_user_by_id(emp)
            user.time_entries.append(DailyPonto(
                user_id=emp,
                entry_date=date(2026, 5, 13),
                arrival=time(10, 0),
                lunch_start=time(12, 0),
                lunch_end=time(13, 0),
                departure=time(17, 0),
                status=PontoStatus.LATE,
            ))
            uow.commit()
        _login(client, mgr)
        r = client.post(
            f"/manager/add-attestation/{emp}",
            data={
                "start_date": "2026-05-13",
                "end_date": "2026-05-13",
                "cid": "J00",
                "start_time": "09:00",
                "end_time": "11:00",
            },
        )
        assert r.status_code == 302
        with uow:
            user = uow.users.get_user_by_id(emp)
            ponto = next(p for p in user.time_entries if p.entry_date == date(2026, 5, 13))
            assert ponto.status == PontoStatus.DISMISSED
            assert ponto.excused_minutes == 60
            assert ponto.manager_notes and "J00" in ponto.manager_notes
            assert ponto.arrival_late_excused
            assert ponto.arrival_late_reviewed
            assert user.total_balance == -60

    def test_attestation_is_audited(self, client, uow):
        mgr = _create_manager(uow)
        emp = _create_user(uow, "emp_att_audit@test.com", complete_profile=True, with_schedule=True)
        _add_ponto(uow, emp, date(2026, 5, 17), status=PontoStatus.MISSING)
        _login(client, mgr)
        client.post(
            f"/manager/add-attestation/{emp}",
            data={"start_date": "2026-05-17", "end_date": "2026-05-17", "cid": "J02"},
        )
        with uow:
            from sqlalchemy import select
            from src.domain.model import AuditLog
            logs = uow.session.execute(select(AuditLog)).scalars().all()
            assert any(
                log.action == "ADD_ATTESTATION"
                and log.target_id == emp
                and log.details and "J02" in log.details
                for log in logs
            )

    def test_invalid_partial_time_rejected(self, client, uow):
        mgr = _create_manager(uow)
        emp = _create_user(uow, "emp_att_bad@test.com", complete_profile=True, with_schedule=True)
        _login(client, mgr)
        r = client.post(
            f"/manager/add-attestation/{emp}",
            data={
                "start_date": "2026-05-18",
                "end_date": "2026-05-18",
                "cid": "J03",
                "start_time": "11:00",
                "end_time": "09:00",
            },
        )
        assert r.status_code == 302
        with uow:
            user = uow.users.get_user_by_id(emp)
            assert not any(p.entry_date == date(2026, 5, 18) for p in user.time_entries)
            assert not user.is_on_attestation(date(2026, 5, 18))


class TestVacation:
    def test_vacation_keeps_dismissed_logs(self, client, uow):
        mgr = _create_manager(uow)
        emp = _create_user(uow, "vac_emp1@test.com", complete_profile=True, with_schedule=True)
        _add_ponto(uow, emp, date(2026, 5, 25), status=PontoStatus.MISSING)
        _login(client, mgr)
        r = client.post(
            f"/manager/add-vacation/{emp}",
            data={"start_date": "2026-05-25", "end_date": "2026-05-26"},
        )
        assert r.status_code == 302
        with uow:
            user = uow.users.get_user_by_id(emp)
            ponto = next(p for p in user.time_entries if p.entry_date == date(2026, 5, 25))
            assert ponto.status == PontoStatus.DISMISSED
            assert ponto.manager_notes == "Férias"
            assert any(p.entry_date == date(2026, 5, 26) and p.status == PontoStatus.DISMISSED for p in user.time_entries)
            assert user.is_on_vacation(date(2026, 5, 25))


class TestFacultativo:
    def test_full_day_facultativo_dismisses_all_employees(self, client, uow):
        mgr = _create_manager(uow)
        emp1 = _create_user(uow, "fac_emp1@test.com", complete_profile=True, with_schedule=True)
        emp2 = _create_user(uow, "fac_emp2@test.com", complete_profile=True, with_schedule=True)
        _add_ponto(uow, emp1, date(2026, 5, 20), status=PontoStatus.MISSING)
        _add_ponto(uow, emp2, date(2026, 5, 20), status=PontoStatus.LATE)
        _login(client, mgr)
        r = client.post(
            "/manager/add-facultativo",
            data={"start_date": "2026-05-20", "end_date": "2026-05-20", "description": "Aniversário da cidade"},
        )
        assert r.status_code == 302
        with uow:
            for emp_id in (emp1, emp2):
                user = uow.users.get_user_by_id(emp_id)
                ponto = next(p for p in user.time_entries if p.entry_date == date(2026, 5, 20))
                assert ponto.status == PontoStatus.DISMISSED
                assert ponto.manager_notes and "Ponto facultativo" in ponto.manager_notes

    def test_partial_facultativo_credits_missed_minutes(self, client, uow):
        mgr = _create_manager(uow)
        emp = _create_user(uow, "fac_emp_part@test.com", complete_profile=True, with_schedule=True)
        with uow:
            user = uow.users.get_user_by_id(emp)
            user.time_entries.append(DailyPonto(
                user_id=emp,
                entry_date=date(2026, 5, 21),
                arrival=time(10, 0),
                lunch_start=time(12, 0),
                lunch_end=time(13, 0),
                departure=time(17, 0),
                status=PontoStatus.LATE,
            ))
            uow.commit()
        _login(client, mgr)
        r = client.post(
            "/manager/add-facultativo",
            data={
                "start_date": "2026-05-21",
                "end_date": "2026-05-21",
                "description": "Véspera de feriado",
                "start_time": "09:00",
                "end_time": "11:00",
            },
        )
        assert r.status_code == 302
        with uow:
            user = uow.users.get_user_by_id(emp)
            ponto = next(p for p in user.time_entries if p.entry_date == date(2026, 5, 21))
            assert ponto.status == PontoStatus.DISMISSED
            assert ponto.excused_minutes == 60
            assert user.total_balance == -60
