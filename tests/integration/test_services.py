import pytest
from src.service_layer import services
from src.domain.model import UserRole
from datetime import date, time

def test_register_user(uow):
    services.register_user(uow, "test@example.com", "password123")
    with uow:
        user = uow.users.get_user_by_email("test@example.com")
        assert user is not None
        assert user.email == "test@example.com"
        assert user.role == UserRole.EMPLOYEE

def test_cannot_register_duplicate_user(uow):
    services.register_user(uow, "test@example.com", "password123")
    with pytest.raises(ValueError, match="already exists"):
        services.register_user(uow, "test@example.com", "password456")

def test_update_user_profile(uow):
    services.register_user(uow, "test@example.com", "password123")
    with uow:
        user = uow.users.get_user_by_email("test@example.com")
        user_id = user.user_id

    services.update_user_profile(
        uow, user_id, "REG123", "123.456.789-00", "IT", "Dev", "Admin", "John Doe"
    )

    with uow:
        user = uow.users.get_user_by_id(user_id)
        assert user.profile.registration_number == "REG123"
        assert user.is_profile_complete is True

def test_clock_in_out_flow(uow):
    services.register_user(uow, "test@example.com", "password123")
    with uow:
        user = uow.users.get_user_by_email("test@example.com")
        user_id = user.user_id

    # Simulate clock in (Chegada)
    msg = services.clock_in_out(uow, user_id, "Office")
    assert msg == "Chegada registrada"
    
    # Simulate Saída Almoço
    msg = services.clock_in_out(uow, user_id, "Office")
    assert msg == "Saída para almoço registrada"
    
    with uow:
        user = uow.users.get_user_by_id(user_id)
        ponto = user.time_entries[0]
        assert ponto.arrival is not None
        assert ponto.lunch_start is not None
        assert "Chegada: Office" in ponto.location_data
        assert "Almoço (Sai): Office" in ponto.location_data

def test_generate_excel_report(uow):
    services.register_user(uow, "test@example.com", "password123")
    with uow:
        user = uow.users.get_user_by_email("test@example.com")
        user_id = user.user_id
    
    services.clock_in_out(uow, user_id, "Office")
    
    excel_file = services.generate_excel_report(uow, user_id)
    assert excel_file is not None
    assert excel_file.getbuffer().nbytes > 0
