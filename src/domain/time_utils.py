"""Shared helpers for time arithmetic used across the domain and service layers."""
from datetime import date, datetime, time, timedelta


def minutes_between(start: time, end: time) -> int:
        """Return whole minutes between two times, ignoring the calendar day."""
        if not start or not end:
                return 0
        diff = datetime.combine(date.min, end) - datetime.combine(date.min, start)
        return int(diff.total_seconds() / 60)


def limit_after(base: time, tolerance_minutes: int, day: date) -> time:
        """Time point tolerance minutes after the expected base time."""
        return (datetime.combine(day, base) + timedelta(minutes=tolerance_minutes)).time()


def limit_before(base: time, tolerance_minutes: int, day: date) -> time:
        """Time point tolerance minutes before the expected base time."""
        return (datetime.combine(day, base) - timedelta(minutes=tolerance_minutes)).time()
