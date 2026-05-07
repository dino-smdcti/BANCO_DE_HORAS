from datetime import date, time
from src.domain.model import DailyPonto, User, UserRole, WorkSchedule
from src.service_layer.services import clock_in_out
from unittest.mock import MagicMock

def test_placeholder_dynamic_calculation():
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
    
    # Verify placeholders are calculated dynamically
    assert ponto.get_placeholder("lunch_start", schedule) == time(12, 0)
    assert ponto.get_placeholder("lunch_end", schedule) == time(13, 0)
    assert ponto.get_placeholder("departure", schedule) == time(17, 0)
    
    # Verify arrival is real, not placeholder
    assert ponto.arrival is not None
    assert ponto.get_placeholder("arrival", schedule) is None

def test_placeholder_disappears_on_clock_in():
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
    
    # Verify lunch_start is now real
    assert ponto.lunch_start is not None
    assert ponto.get_placeholder("lunch_start", schedule) is None
    # Verify lunch_end is still a placeholder
    assert ponto.get_placeholder("lunch_end", schedule) == time(13, 0)
