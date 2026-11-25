from datetime import date, time

from src.domain.model import WorkSchedule, DailyPonto, User, UserRole
from src.service_layer.clock_service import (
        _flag_if_lunch_start_late,
        _flag_if_lunch_start_early,
        _re_evaluate_anomalies,
)

DAY = date(2026, 5, 4)


def _schedule():
        return WorkSchedule(
                user_id=1,
                expected_arrival=time(8, 0),
                expected_lunch_start=time(12, 0),
                expected_lunch_end=time(13, 0),
                expected_departure=time(17, 0),
                tolerance_minutes=10,
                has_lunch_break=True,
        )


def _user():
        return User(email="emp@test.com", password_hash="!", role=UserRole.EMPLOYEE, work_schedule=_schedule())


def _ponto(lunch_start):
        return DailyPonto(user_id=1, entry_date=DAY, lunch_start=lunch_start)


class TestClockTimeFlags:
        def test_late_when_after_window(self):
                p = _ponto(time(12, 30))
                _flag_if_lunch_start_late(None, p, _user(), DAY, time(12, 30))
                _flag_if_lunch_start_early(None, p, _user(), DAY, time(12, 30))
                assert p.lunch_start_late
                assert not p.lunch_start_early

        def test_early_when_before_window(self):
                p = _ponto(time(11, 30))
                _flag_if_lunch_start_late(None, p, _user(), DAY, time(11, 30))
                _flag_if_lunch_start_early(None, p, _user(), DAY, time(11, 30))
                assert p.lunch_start_early
                assert not p.lunch_start_late

        def test_no_flag_within_tolerance(self):
                p = _ponto(time(12, 5))
                _flag_if_lunch_start_late(None, p, _user(), DAY, time(12, 5))
                _flag_if_lunch_start_early(None, p, _user(), DAY, time(12, 5))
                assert not p.lunch_start_late
                assert not p.lunch_start_early


class TestReEvaluate:
        def test_re_evaluate_flags_late(self):
                p = _ponto(time(13, 0))
                _re_evaluate_anomalies(p, _schedule(), DAY)
                assert p.lunch_start_late
                assert not p.lunch_start_early

        def test_re_evaluate_flags_early(self):
                p = _ponto(time(11, 0))
                _re_evaluate_anomalies(p, _schedule(), DAY)
                assert p.lunch_start_early
                assert not p.lunch_start_late

        def test_re_evaluate_ignores_within_tolerance(self):
                p = _ponto(time(12, 5))
                _re_evaluate_anomalies(p, _schedule(), DAY)
                assert not p.lunch_start_late
                assert not p.lunch_start_early


class TestNeutralization:
        def test_approved_early_lunch_start_neutralizes_to_expected(self):
                sched = _schedule()
                user = User(email="emp@test.com", password_hash="!", role=UserRole.EMPLOYEE, work_schedule=sched)
                ponto = DailyPonto(user_id=1, entry_date=DAY)
                user.time_entries.append(ponto)
                ponto.arrival = time(8, 0)
                ponto.lunch_start = time(10, 0)
                ponto.lunch_end = time(13, 0)
                ponto.departure = time(17, 0)
                ponto.lunch_start_early = True
                ponto.lunch_start_early_approved = True
                # Neutralized to expected 12:00 -> 08:00-12:00 + 13:00-17:00 = 480 -> balance 0
                assert user.total_balance == 0
