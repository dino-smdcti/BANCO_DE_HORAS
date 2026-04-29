import pytest
from unittest.mock import patch
from src.entrypoints.flask_app import app, serializer
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer import services

@pytest.fixture
def client(session_factory):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    
    # Patch the session factory in SqlAlchemyUnitOfWork
    with patch("src.entrypoints.flask_app.SqlAlchemyUnitOfWork", lambda: SqlAlchemyUnitOfWork(session_factory)):
        with app.test_client() as client:
            yield client

def test_forgot_password_sends_email(client, uow):
    # Register a user
    services.register_user(uow, "test@example.com", "password123")
    
    with patch("src.entrypoints.flask_app.send_email") as mock_send:
        mock_send.return_value = True
        
        response = client.post("/forgot-password", data={"email": "test@example.com"}, follow_redirects=True)
        
        assert response.status_code == 200
        assert b"Se o e-mail estiver cadastrado" in response.data
        
        mock_send.assert_called_once()
        args, _ = mock_send.call_args
        assert args[0] == "test@example.com"
        assert "Recuperação de Senha" in args[1]
        assert "reset-password" in args[2]

def test_reset_password_updates_hash(client, uow):
    # Register a user
    services.register_user(uow, "test@example.com", "password123")
    
    token = serializer.dumps("test@example.com", salt="password-reset-salt")
    
    response = client.post(f"/reset-password/{token}", data={"password": "newpassword123"}, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Sua senha foi atualizada com sucesso" in response.data
    
    # Verify login with new password
    with uow:
        user = uow.users.get_user_by_email("test@example.com")
        from werkzeug.security import check_password_hash
        assert check_password_hash(user.password_hash, "newpassword123")

def test_magic_login_sends_email(client, uow):
    services.register_user(uow, "magic@example.com", "password123")
    
    with patch("src.entrypoints.flask_app.send_email") as mock_send:
        mock_send.return_value = True
        
        response = client.post("/magic-login", data={"email": "magic@example.com"}, follow_redirects=True)
        
        assert response.status_code == 200
        assert b"Se o e-mail estiver cadastrado" in response.data
        
        mock_send.assert_called_once()
        args, _ = mock_send.call_args
        assert args[0] == "magic@example.com"
        assert "Link de Acesso" in args[1]
        assert "login-link" in args[2]

def test_magic_link_login_works(client, uow):
    services.register_user(uow, "magic@example.com", "password123")
    
    token = serializer.dumps("magic@example.com", salt="magic-login-salt")
    
    response = client.get(f"/login-link/{token}", follow_redirects=True)
    
    assert response.status_code == 200
    # Should redirect to complete profile if not complete, or dashboard
    # By default register_user doesn't complete profile
    assert b"Profile completion" in response.data or "complete-profile" in response.request.path or b"Dashboard" in response.data
