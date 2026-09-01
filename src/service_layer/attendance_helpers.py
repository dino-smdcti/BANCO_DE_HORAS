from datetime import timedelta

from src.domain.time_utils import minutes_between
from src.config import ANOMALY_FLAG_TRIPLES


def _ponto_for(employee, day):
        for entry in employee.time_entries:
                if entry.entry_date == day:
                        return entry
        return None


def _require_user(uow, user_id):
        user = uow.users.get_user_by_id(user_id)
        if not user:
                raise ValueError("User not found.")
        return user


def _daterange(start_date, end_date):
        day = start_date
        while day <= end_date:
                yield day
                day += timedelta(days=1)


def _validate_period(start_date, end_date, start_time, end_time):
        if end_date < start_date:
                raise ValueError("Período inválido.")
        partial = start_time is not None or end_time is not None
        if partial and (start_time is None or end_time is None):
                raise ValueError("Informe o horário de início e fim.")
        if partial and end_time <= start_time:
                raise ValueError("Horário inválido.")


def _excuse_all_stages(ponto):
        for reviewed, approved, excused in ANOMALY_FLAG_TRIPLES:
                setattr(ponto, reviewed, True)
                setattr(ponto, excused, True)
        setattr(ponto, "missing_reviewed", True)
        setattr(ponto, "missing_excused", True)


def _reset_all_excuses(ponto):
        for reviewed, approved, excused in ANOMALY_FLAG_TRIPLES:
                setattr(ponto, reviewed, False)
                setattr(ponto, approved, False)
                setattr(ponto, excused, False)
        ponto.missing_reviewed = False
        ponto.missing_approved = False
        ponto.missing_excused = False


def _excused_minutes(schedule, start_time, end_time, arrival, lunch_start, lunch_end, departure):
        """Minutes of the interval that fall inside the expected workday but were not actually worked."""
        if not schedule:
                return 0
        expected = _schedule_intervals(schedule)
        clocked = _clocked_intervals(arrival, lunch_start, lunch_end, departure, schedule.has_lunch_break)
        total = sum(_overlap_minutes(start_time, end_time, a, b) for a, b in expected)
        worked = sum(_overlap_minutes(start_time, end_time, a, b) for a, b in clocked)
        return max(0, total - worked)


def _schedule_intervals(schedule):
        if schedule.has_lunch_break and schedule.expected_lunch_start and schedule.expected_lunch_end:
                return [
                        (schedule.expected_arrival, schedule.expected_lunch_start),
                        (schedule.expected_lunch_end, schedule.expected_departure),
                ]
        return [(schedule.expected_arrival, schedule.expected_departure)]


def _clocked_intervals(arrival, lunch_start, lunch_end, departure, has_lunch_break):
        if has_lunch_break and lunch_start and lunch_end:
                intervals = []
                if arrival:
                        intervals.append((arrival, lunch_start))
                if departure:
                        intervals.append((lunch_end, departure))
                return intervals
        if arrival and departure:
                return [(arrival, departure)]
        return []


def _overlap_minutes(s1, e1, s2, e2):
        start = max(s1, s2)
        end = min(e1, e2)
        if end <= start:
                return 0
        return minutes_between(start, end)