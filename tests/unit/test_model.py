from datetime import date, time
from src.domain.model import DailyPonto, UserProfile, User, UserRole

def test_daily_ponto_worked_minutes():
    ponto = DailyPonto(
        user_id=1,
        entry_date=date(2026, 4, 28),
        arrival=time(8, 0),
        lunch_start=time(12, 0),
        lunch_end=time(13, 0),
        departure=time(17, 0)
    )
    # (12-8) = 4 hours = 240 mins
    # (17-13) = 4 hours = 240 mins
    # Total = 480 mins
    assert ponto.worked_minutes == 480

def test_daily_ponto_incomplete_worked_minutes():
    ponto = DailyPonto(
        user_id=1,
        entry_date=date(2026, 4, 28),
        arrival=time(8, 0)
    )
    assert ponto.worked_minutes == 0

def test_user_profile_is_complete():
    profile = UserProfile(
        registration_number="123",
        cpf="111.111.111-11",
        department="IT",
        position="Dev",
        secretariat="Admin",
        full_name="John Doe"
    )
    assert profile.is_complete() is True

def test_user_profile_is_incomplete():
    profile = UserProfile(full_name="John Doe")
    assert profile.is_complete() is False

def test_user_is_manager():
    user = User(email="test@test.com", password_hash="hash", role=UserRole.MANAGER)
    assert user.is_manager is True
    assert user.role == UserRole.MANAGER
