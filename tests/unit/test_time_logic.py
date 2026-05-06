
from datetime import date, time
from src.domain.model import DailyPonto, User, UserRole, WorkSchedule

def test_daily_balance_calculation_8h_target():
    # User works 8h (480 mins) exactly, should have 0 balance
    schedule = WorkSchedule(user_id=1, expected_arrival=time(8,0), expected_lunch_start=time(12,0), expected_lunch_end=time(13,0), expected_departure=time(17,0))
    user = User(email="test@test.com", password_hash="hash", role=UserRole.EMPLOYEE, work_schedule=schedule)
    ponto = DailyPonto(
        user_id=1,
        entry_date=date(2026, 5, 4),
        arrival=time(8, 0),
        lunch_start=time(12, 0),
        lunch_end=time(13, 0),
        departure=time(17, 0)
    )
    user.time_entries.append(ponto)
    # 8-12 = 4h (240m), 13-17 = 4h (240m) = 480m. Expected 480m. Balance 0.
    assert user.total_balance == 0

def test_daily_balance_calculation_overtime():
    # User works 9h, should have +60 balance
    schedule = WorkSchedule(user_id=1, expected_arrival=time(8,0), expected_lunch_start=time(12,0), expected_lunch_end=time(13,0), expected_departure=time(17,0))
    user = User(email="test@test.com", password_hash="hash", role=UserRole.EMPLOYEE, work_schedule=schedule)
    ponto = DailyPonto(
        user_id=1,
        entry_date=date(2026, 5, 4),
        arrival=time(8, 0),
        lunch_start=time(12, 0),
        lunch_end=time(13, 0),
        departure=time(18, 0)
    )
    user.time_entries.append(ponto)
    # 8-12 = 240m, 13-18 = 300m = 540m. 540 - 480 = 60.
    assert user.total_balance == 60

def test_manager_time_tracking():
    # Manager, should now be tracked against the 8-hour target
    schedule = WorkSchedule(user_id=2, expected_arrival=time(8,0), expected_lunch_start=time(12,0), expected_lunch_end=time(13,0), expected_departure=time(17,0))
    user = User(email="mgr@test.com", password_hash="hash", role=UserRole.MANAGER, work_schedule=schedule)
    ponto = DailyPonto(
        user_id=2,
        entry_date=date(2026, 5, 4),
        arrival=time(10, 0),
        lunch_start=time(12, 0),
        lunch_end=time(12, 0),
        departure=time(14, 0)
    )
    user.time_entries.append(ponto)
    # Worked 10-14 = 4h = 240 mins. Expected 480. Balance: 240 - 480 = -240.
    assert user.total_balance == -240

def test_daily_balance_calculation_no_lunch_break():
    # Schedule with no lunch break
    schedule = WorkSchedule(user_id=1, expected_arrival=time(8,0), expected_lunch_start=None, expected_lunch_end=None, expected_departure=time(16,0), has_lunch_break=False)
    user = User(email="test@test.com", password_hash="hash", role=UserRole.EMPLOYEE, work_schedule=schedule)
    ponto = DailyPonto(
        user_id=1,
        entry_date=date(2026, 5, 4),
        arrival=time(8, 0),
        departure=time(16, 0),
        has_lunch_break=False
    )
    user.time_entries.append(ponto)
    # Worked 8-16 = 8h (480m). Expected 480m. Balance 0.
    assert user.total_balance == 0

def test_incomplete_entry_status_unknown():
    # Incomplete entry in past = unknown
    ponto = DailyPonto(
        user_id=1,
        entry_date=date(2025, 1, 1), # Past
        arrival=time(8, 0)
    )
    assert ponto.status_label == "Desconhecido"
