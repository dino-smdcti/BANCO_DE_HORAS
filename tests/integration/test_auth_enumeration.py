import pytest
from unittest.mock import patch

from src.entrypoints.flask_app import app, serializer
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture
def client(session_factory):
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


def test_magic_link_login_unknown_user_generic_message(client, uow):
    token = serializer.dumps("ghost@test.com", salt="magic-login-salt")
    response = client.get(f"/login-link/{token}", follow_redirects=True)
    body = response.get_data(as_text=True)
    assert "Usuário não encontrado" not in body
    assert "O link de acesso é inválido ou expirou" in body
