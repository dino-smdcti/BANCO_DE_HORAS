import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from src.entrypoints.flask_app import app
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.domain.model import User, PontoStatus, DailyPonto

@pytest.fixture
def client(session_factory):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with patch("src.entrypoints.flask_app.SqlAlchemyUnitOfWork", lambda: SqlAlchemyUnitOfWork(session_factory)):
        with app.test_client() as client:
            yield client

from werkzeug.security import generate_password_hash, check_password_hash

def test_password_change_flow(client, uow):
    # Setup user
    with uow:
        email = "unique_test@example.com"
        old_password = "old_password123"
        old_hash = generate_password_hash(old_password)
        user = User(email=email, password_hash=old_hash, role="employee")
        uow.session.add(user)
        uow.commit()
        user_id = user.user_id
    
    # Login and change password
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
    
    new_password = "completely_new_password_that_must_hash_differently"
    # Test POST /profile
    client.post("/profile", data={
        "email": email,
        "password": new_password,
        "start_analysis_date": "2026-01-01"
    }, follow_redirects=True)
    
    # Verify hash changed
    with uow:
        user = uow.users.get_user_by_id(user_id)
        uow.session.refresh(user)
        assert check_password_hash(user.password_hash, new_password)
        assert not check_password_hash(user.password_hash, old_password)

def test_daily_log_check_logic():
    from src.adapters.orm import start_mappers
    start_mappers()
    from src.service_layer.check_logic import check_for_missing_logs
    
    mock_uow = MagicMock()
    
    # Mock date to be "today"
    with patch("src.service_layer.check_logic.date") as mock_date:
        mock_date.today.return_value = date(2026, 5, 12)
        mock_date.fromisoformat = date.fromisoformat
        
        # Mock last_check_date to be 2026-05-10
        with patch("src.service_layer.check_logic.get_last_check", return_value=date(2026, 5, 10)):
            with patch("src.service_layer.check_logic.set_last_check") as mock_set:
                check_for_missing_logs(mock_uow)
                
                # Assert check was performed
                assert mock_uow.users.list_employees.called
                mock_set.assert_called_with(date(2026, 5, 12))
