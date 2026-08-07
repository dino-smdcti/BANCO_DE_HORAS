
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

def test_total_balance_only_complete_days():
    schedule = WorkSchedule(user_id=1, expected_arrival=time(8,0), expected_lunch_start=time(12,0), expected_lunch_end=time(13,0), expected_departure=time(17,0))
    user = User(email="test@test.com", password_hash="hash", role=UserRole.EMPLOYEE, work_schedule=schedule)
    
    # Complete day (9h worked -> +60 balance)
    ponto1 = DailyPonto(user_id=1, entry_date=date(2026, 5, 4), arrival=time(8, 0), lunch_start=time(12, 0), lunch_end=time(13, 0), departure=time(18, 0))
    # Incomplete day (only arrival -> should be ignored)
    ponto2 = DailyPonto(user_id=1, entry_date=date(2026, 5, 5), arrival=time(8, 0))
    
    user.time_entries.extend([ponto1, ponto2])
    
    # Only ponto1 counts as 60. Ponto2 counts as -480 (8h penalty).
    # Total: 60 - 480 = -420
    assert user.total_balance == -420

def test_incomplete_entry_status_unknown():
    # Incomplete entry in past = unknown
    ponto = DailyPonto(
        user_id=1,
        entry_date=date(2025, 1, 1), # Past
        arrival=time(8, 0)
    )
    assert ponto.status_label == "Desconhecido"


def _user_with_schedule(schedule, entry_date=date(2026, 5, 4)):
    user = User(email="t@test.com", password_hash="!", role=UserRole.EMPLOYEE, work_schedule=schedule)
    user.time_entries.append(DailyPonto(user_id=1, entry_date=entry_date))
    return user


def _lunch_schedule():
    return WorkSchedule(user_id=1, expected_arrival=time(8,0), expected_lunch_start=time(12,0),
                        expected_lunch_end=time(13,0), expected_departure=time(17,0), has_lunch_break=True)


def test_partial_log_without_lunch_clocks_is_penalized():
    # Arrival + departure recorded but no lunch clocks: the lunch window is unverified,
    # so it must not be credited as worked (was +60, now penalized like an incomplete day).
    user = _user_with_schedule(_lunch_schedule())
    ponto = user.time_entries[0]
    ponto.arrival = time(8, 0)
    ponto.departure = time(17, 0)
    assert ponto.worked_minutes == 0
    assert user.total_balance == -480


def test_partial_log_only_counts_verified_intervals():
    # Only the morning interval is bounded by real clocks (08:00 arrival, 12:00 lunch out).
    user = _user_with_schedule(_lunch_schedule())
    ponto = user.time_entries[0]
    ponto.arrival = time(8, 0)
    ponto.lunch_start = time(12, 0)
    assert ponto.worked_minutes == 240
    assert user.total_balance == -240


def test_approved_late_arrival_preserves_overtime():
    # Late arrival (08:30) is approved, so only the arrival is neutralized to 08:00.
    # The 18:00 departure is real overtime and must still count: 08:00-12:00 + 13:00-18:00 = 540.
    user = _user_with_schedule(_lunch_schedule())
    ponto = user.time_entries[0]
    ponto.arrival = time(8, 30)
    ponto.lunch_start = time(12, 0)
    ponto.lunch_end = time(13, 0)
    ponto.departure = time(18, 0)
    ponto.arrival_late = True
    ponto.arrival_late_approved = True
    assert user.total_balance == 60


def test_excused_early_departure_neutralizes_only_that_stage():
    # Early departure (16:30) is excused -> departure treated as expected 17:00 -> 480 -> 0.
    user = _user_with_schedule(_lunch_schedule())
    ponto = user.time_entries[0]
    ponto.arrival = time(8, 0)
    ponto.lunch_start = time(12, 0)
    ponto.lunch_end = time(13, 0)
    ponto.departure = time(16, 30)
    ponto.departure_early = True
    ponto.departure_early_excused = True
    assert user.total_balance == 0


def test_approved_anomaly_with_unverified_lunch_still_penalized():
    # Approved late arrival does not create credit for a lunch window that was never clocked.
    user = _user_with_schedule(_lunch_schedule())
    ponto = user.time_entries[0]
    ponto.arrival = time(8, 30)
    ponto.departure = time(18, 0)
    ponto.arrival_late = True
    ponto.arrival_late_approved = True
    assert user.total_balance == -480
