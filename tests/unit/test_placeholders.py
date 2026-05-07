from datetime import date, time
from src.domain.model import DailyPonto, User, UserRole, WorkSchedule
from src.service_layer.services import clock_in_out
from unittest.mock import MagicMock

def test_placeholder_initialization_on_arrival():
    # Setup user and schedule
    schedule = WorkSchedule(
        user_id=1, 
        expected_arrival=time(8, 0), 
        expected_lunch_start=time(12, 0), 
        expected_lunch_end=time(13, 0), 
        expected_departure=time(17, 0)
    )
    user = User(email="test@test.com", password_hash="hash", role=UserRole.EMPLOYEE, work_schedule=schedule)
    
    # Mock UOW
    uow = MagicMock()
    uow.users.get_user_by_id.return_value = user
    
    # Trigger clock-in
    clock_in_out(uow, user_id=1, stage="arrival")
    
    ponto = user.time_entries[0]
    
    # Verify placeholders
    assert ponto.lunch_start == time(12, 0)
    assert ponto.lunch_start_is_placeholder is True
    assert ponto.lunch_end == time(13, 0)
    assert ponto.lunch_end_is_placeholder is True
    assert ponto.departure == time(17, 0)
    assert ponto.departure_is_placeholder is True
    
    # Verify real time
    assert ponto.arrival_is_placeholder is False
    assert ponto.arrival is not None

def test_placeholder_swap_on_clock_out():
    # Setup user and schedule
    schedule = WorkSchedule(
        user_id=1, 
        expected_arrival=time(8, 0), 
        expected_lunch_start=time(12, 0), 
        expected_lunch_end=time(13, 0), 
        expected_departure=time(17, 0)
    )
    user = User(email="test@test.com", password_hash="hash", role=UserRole.EMPLOYEE, work_schedule=schedule)
    
    # Mock UOW
    uow = MagicMock()
    uow.users.get_user_by_id.return_value = user
    
    # Clock in
    clock_in_out(uow, user_id=1, stage="arrival")
    
    # Clock out for lunch
    clock_in_out(uow, user_id=1, stage="lunch_start")
    
    ponto = user.time_entries[0]
    
    assert ponto.lunch_start_is_placeholder is False
    assert ponto.lunch_start is not None
    assert ponto.lunch_end_is_placeholder is True # Still placeholder
