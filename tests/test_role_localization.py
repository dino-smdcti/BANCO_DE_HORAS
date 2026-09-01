import pytest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from src.entrypoints.flask_app import app


@pytest.fixture
def client(session_factory):
    from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    patcher = patch("src.entrypoints.flask_app.process_daily_absences", lambda uow: None)
    patcher.start()
    try:
        with patch("src.entrypoints.flask_app.SqlAlchemyUnitOfWork",
                   lambda: SqlAlchemyUnitOfWork(session_factory)):
            with app.test_client() as c:
                yield c
    finally:
        patcher.stop()


def _make_user(uow, email, role, full_name):
    from src.domain.model import User, UserProfile
    with uow:
        user = User(email=email, password_hash=generate_password_hash("pass"), role=role,
                    profile=UserProfile(full_name=full_name, cpf="12345678901",
                                        department="dept", position="pos", secretariat="sec"))
        uow.session.add(user)
        uow.commit()
        return user.user_id


def _login(client, uid):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)


def test_admin_dashboard_shows_all_role_titles(client, uow):
    admin = _make_user(uow, "admin@test.com", "admin", "Secretário Geral")
    _make_user(uow, "manager@test.com", "manager", "Diretor Geral")
    _make_user(uow, "employee@test.com", "employee", "Funcionário Padrão")
    _login(client, admin)
    response = client.get("/management")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Secretário" in body
    assert "Diretor" in body
    assert "Funcionário" in body
