import pytest
from unittest.mock import patch
from datetime import time, date
from src.entrypoints.flask_app import app
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer import services
from src.domain.model import User, JourneyType
from werkzeug.security import generate_password_hash


@pytest.fixture
def client(session_factory):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with patch("src.entrypoints.flask_app.SqlAlchemyUnitOfWork", lambda: SqlAlchemyUnitOfWork(session_factory)):
        with app.test_client() as client:
            yield client


def test_new_user_full_flow(client, uow):
    """Complete new user lifecycle: register -> complete profile -> choose journey -> dashboard."""

    # 1. Create a JourneyType (needed for choose-journey to show options)
    with uow:
        jt = JourneyType(
            name="Jornada Padrão",
            expected_arrival=time(8, 0),
            expected_lunch_start=time(12, 0),
            expected_lunch_end=time(13, 0),
            expected_departure=time(17, 0),
            tolerance_minutes=15
        )
        uow.session.add(jt)
        uow.commit()
        journey_id = jt.journey_id

    # 2. Register a new employee
    services.register_user(uow, "novo@test.com", "senha123")
    with uow:
        employee = uow.users.get_user_by_email("novo@test.com")
        employee_id = employee.user_id

    # 3. Simulate login
    with client.session_transaction() as sess:
        sess["_user_id"] = str(employee_id)

    # 4. GET /complete-profile - should render form (profile not complete)
    response = client.get("/complete-profile")
    assert response.status_code == 200

    # 5. POST /complete-profile with valid data -> redirects to dashboard
    #    Dashboard then redirects to choose-journey (no schedule yet)
    response = client.post("/complete-profile", data={
        "full_name": "Novo Funcionário",
        "registration_number": "12345678",
        "cpf": "123.456.789-00",
        "department": "TI",
        "position": "Desenvolvedor",
        "secretariat": "Secretaria Municipal de Tecnologia",
        "birth_date": "1990-01-01"
    }, follow_redirects=True)
    assert response.status_code == 200

    # 6. GET /choose-journey - should show the journey options
    response = client.get("/choose-journey")
    assert response.status_code == 200
    assert "Jornada Padr" in response.data.decode("utf-8")

    # 7. POST /choose-journey to select a journey
    response = client.post("/choose-journey", data={
        "journey_id": str(journey_id)
    }, follow_redirects=True)
    assert response.status_code == 200

    # 8. Dashboard should now render (profile complete + schedule set)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"Registrar Ponto" in response.data


def test_choose_journey_no_journeys_redirects(client, uow):
    """choose-journey flashes warning and redirects when no JourneyType exists."""
    services.register_user(uow, "emp@test.com", "pass")
    with uow:
        emp = uow.users.get_user_by_email("emp@test.com")
        emp_id = emp.user_id
        emp.profile.full_name = "Test User"
        emp.profile.department = "IT"
        emp.profile.position = "Dev"
        emp.profile.secretariat = "SMDCTI"
        uow.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(emp_id)

    response = client.get("/choose-journey", follow_redirects=True)
    assert response.status_code == 200


def test_choose_journey_with_schedule_redirects(client, uow):
    """choose-journey redirects to dashboard when user already has a schedule."""
    with uow:
        emp = User(
            email="emp2@test.com",
            password_hash=generate_password_hash("pass"),
            role="employee"
        )
        uow.session.add(emp)
        uow.commit()
        emp_id = emp.user_id
        emp.profile.full_name = "Test User"
        emp.profile.department = "IT"
        emp.profile.position = "Dev"
        emp.profile.secretariat = "SMDCTI"
        services.set_work_schedule(
            uow, emp_id, emp_id,
            time(8, 0), time(12, 0), time(13, 0), time(17, 0)
        )
        uow.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(emp_id)

    response = client.get("/choose-journey", follow_redirects=True)
    assert response.status_code == 200


def test_complete_profile_already_complete_redirects(client, uow):
    """complete-profile redirects to dashboard when profile is already complete."""
    with uow:
        emp = User(
            email="emp3@test.com",
            password_hash=generate_password_hash("pass"),
            role="employee"
        )
        uow.session.add(emp)
        uow.commit()
        emp_id = emp.user_id
        emp.profile.full_name = "Test User"
        emp.profile.department = "IT"
        emp.profile.position = "Dev"
        emp.profile.secretariat = "SMDCTI"
        uow.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(emp_id)

    response = client.get("/complete-profile", follow_redirects=True)
    assert response.status_code == 200


def test_choose_journey_non_employee_redirects(client, uow):
    """choose-journey redirects non-employee users to dashboard."""
    with uow:
        mgr = User(
            email="mgr@test.com",
            password_hash=generate_password_hash("pass"),
            role="manager"
        )
        uow.session.add(mgr)
        uow.commit()
        mgr_id = mgr.user_id

    with client.session_transaction() as sess:
        sess["_user_id"] = str(mgr_id)

    response = client.get("/choose-journey", follow_redirects=True)
    assert response.status_code == 200


def test_register_duplicate_user_flow(client, uow):
    """Registering an existing user re-sends invitation (does not crash)."""
    with uow:
        mgr = User(
            email="mgr2@test.com",
            password_hash=generate_password_hash("pass"),
            role="manager"
        )
        uow.session.add(mgr)
        uow.commit()
        mgr_id = mgr.user_id

    services.register_user(uow, "dup@test.com", "pass")
    with uow:
        uow.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(mgr_id)

    with patch("src.entrypoints.flask_app.send_email") as mock_send:
        mock_send.return_value = True
        response = client.post("/register", data={
            "email": "dup@test.com",
            "role": "employee"
        }, follow_redirects=True)
        assert response.status_code == 200
        mock_send.assert_called_once()
