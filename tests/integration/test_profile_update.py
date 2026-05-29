import pytest
from unittest.mock import patch
from src.entrypoints.flask_app import app
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer import services

@pytest.fixture
def client(session_factory):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    # Patch the session factory in SqlAlchemyUnitOfWork
    with patch("src.entrypoints.flask_app.SqlAlchemyUnitOfWork", lambda: SqlAlchemyUnitOfWork(session_factory)):
        with app.test_client() as client:
            # Login required for profile
            # Assuming we need to mock login
            with client.session_transaction() as sess:
                sess['_user_id'] = '1'
            yield client

def test_profile_update_sends_correct_data(client, uow):
    # Setup: Create a user
    services.register_user(uow, "original@example.com", "password123")
    
    # Manually ensure user id 1 exists or adjust to match the test setup
    with uow:
        user = uow.users.get_user_by_email("original@example.com")
        # In test suite, user_id might be 1. 
        # Update email
    
    # POST to /profile
    data = {
        "email": "new@example.com",
        "email_notifications": "on"
    }
    
    response = client.post("/profile", data=data, follow_redirects=True)
    
    assert response.status_code == 200
    
    # Verify in DB
    with uow:
        user = uow.users.get_user_by_id(1)
        assert user.email == "new@example.com"
        assert user.email_notifications_enabled is True
