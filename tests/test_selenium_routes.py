import pytest
from unittest.mock import patch


def _client(app, session_factory):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    patcher = patch("src.entrypoints.flask_app.process_daily_absences", lambda uow: None)
    patcher.start()
    try:
        with patch("src.entrypoints.flask_app.SqlAlchemyUnitOfWork",
                   lambda: __import__("src.service_layer.unit_of_work", fromlist=["SqlAlchemyUnitOfWork"]).SqlAlchemyUnitOfWork(session_factory)):
            with app.test_client() as c:
                yield c
    finally:
        patcher.stop()


@pytest.fixture
def client(session_factory):
    from src.entrypoints.flask_app import app
    yield from _client(app, session_factory)


def test_index_route_renders_landing(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Banco de Horas" in response.get_data(as_text=True)


def test_unauthorized_management_access_redirects_to_login(client):
    response = client.get("/management")
    assert response.status_code == 302
    assert "/login" in response.headers.get("Location", "")


def test_invalid_login_shows_error(client):
    response = client.post("/login", data={"email": "invalid@test.com", "password": "wrong"})
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "E-mail ou senha inválidos" in body


def test_forgot_password_post_returns_success_flash(client, uow):
    with uow:
        from src.domain.model import User
        from werkzeug.security import generate_password_hash
        uow.session.add(User(email="forgot@test.com", password_hash=generate_password_hash("x"),
                             role="employee", password_set=True))
        uow.commit()
    response = client.post("/forgot-password", data={"email": "forgot@test.com"})
    assert response.status_code == 302
    assert "/login" in response.headers.get("Location", "")


def test_forgot_password_unknown_email_stays_generic(client):
    response = client.post("/forgot-password", data={"email": "notexisting@test.com"})
    assert response.status_code == 302
    assert "/login" in response.headers.get("Location", "")
