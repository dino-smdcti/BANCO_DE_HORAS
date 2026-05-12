import unittest
from datetime import date, time
from src.domain.model import User, WorkSchedule, DailyPonto, PontoStatus

class TestTotalBalanceExhaustive(unittest.TestCase):
    def setUp(self):
        # 8h/day schedule (480 mins)
        self.schedule = WorkSchedule(
            user_id=1,
            expected_arrival=time(8, 0),
            expected_lunch_start=time(12, 0),
            expected_lunch_end=time(13, 0),
            expected_departure=time(17, 0)
        )
        self.user = User(email="test@test.com", password_hash="!", role="employee", work_schedule=self.schedule)

    def test_full_8h_day(self):
        self.user.time_entries.append(DailyPonto(
            user_id=1, entry_date=date(2026, 5, 1),
            arrival=time(8, 0), lunch_start=time(12, 0), lunch_end=time(13, 0), departure=time(17, 0)
        ))
        # 480 expected - 480 worked = 0 balance
        self.assertEqual(self.user.total_balance, 0)

    def test_early_departure_short_lunch(self):
        # Worked 08:00-12:00 (4h) and 12:30-16:00 (3.5h) = 7.5h (450m)
        self.user.time_entries.append(DailyPonto(
            user_id=1, entry_date=date(2026, 5, 1),
            arrival=time(8, 0), lunch_start=time(12, 0), lunch_end=time(12, 30), departure=time(16, 0)
        ))
        # (450 - 480) = -30m balance
        self.assertEqual(self.user.total_balance, -30)

    def test_missing_day_penalty(self):
        self.user.time_entries.append(DailyPonto(
            user_id=1, entry_date=date(2026, 5, 1), status=PontoStatus.MISSING
        ))
        # -480m balance
        self.assertEqual(self.user.total_balance, -480)

    def test_rejected_justification_penalty(self):
        self.user.time_entries.append(DailyPonto(
            user_id=1, entry_date=date(2026, 5, 1), status=PontoStatus.REJECTED
        ))
        # -480m balance
        self.assertEqual(self.user.total_balance, -480)

    def test_no_lunch_break_schedule(self):
        self.user.work_schedule.has_lunch_break = False
        self.user.work_schedule.expected_departure = time(16, 0) # Update target to 8h
        # Expected: 8h = 480m
        # Worked: 08:00 - 16:00 (8h)
        self.user.time_entries.append(DailyPonto(
            user_id=1, entry_date=date(2026, 5, 1),
            arrival=time(8, 0), departure=time(16, 0), has_lunch_break=False
        ))
        self.assertEqual(self.user.total_balance, 0)

if __name__ == "__main__":
    unittest.main()
