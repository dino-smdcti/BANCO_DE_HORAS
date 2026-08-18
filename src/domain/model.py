from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Optional
from enum import Enum
import re

from src.domain.time_utils import minutes_between


class UserRole(str, Enum):
        ADMIN = "admin"
        MANAGER = "manager"
        GESTOR = "gestor"
        EMPLOYEE = "employee"

        @classmethod
        def _missing_(cls, value):
                """Allow case-insensitive lookup of role strings."""
                return _find_member(cls, value, str.lower)


class ScheduleType(str, Enum):
        STANDARD = "STANDARD"
        ROTATION_12X36 = "ROTATION_12X36"

        @classmethod
        def _missing_(cls, value):
                """Resolve case-insensitive and legacy values (e.g. "12X36")."""
                return _resolve_schedule_type(cls, value)


class PontoStatus(str, Enum):
        ON_TIME = "No Horário"
        LATE = "Atrasado"
        MISSING = "Faltante"
        JUSTIFIED = "Justificado"
        REJECTED = "Rejeitado"
        CORRECTED = "Corrigido"
        DISMISSED = "Dispensado"


@dataclass
class CompanySettings:
        lat: float
        lon: float
        start_analysis_date: date = date(2026, 5, 1)


@dataclass
class WorkSchedule:
        user_id: int
        expected_arrival: time
        expected_lunch_start: Optional[time]
        expected_lunch_end: Optional[time]
        expected_departure: time
        tolerance_minutes: int = 15
        has_lunch_break: bool = True
        schedule_type: ScheduleType = ScheduleType.STANDARD
        rotation_start_date: Optional[date] = None
        schedule_id: Optional[int] = None

        def is_work_day(self, target_date: date) -> bool:
                return _is_work_day(self.schedule_type, self.rotation_start_date, target_date)

        def daily_target_minutes(self) -> int:
                return _daily_target(self, self.expected_arrival, self.expected_lunch_start, self.expected_lunch_end, self.expected_departure)


@dataclass
class JourneyType:
        name: str
        expected_arrival: time
        expected_lunch_start: Optional[time]
        expected_lunch_end: Optional[time]
        expected_departure: time
        tolerance_minutes: int = 15
        has_lunch_break: bool = True
        schedule_type: ScheduleType = ScheduleType.STANDARD
        journey_id: Optional[int] = None


@dataclass
class Holiday:
        holiday_date: date
        description: str
        is_mandatory: bool = True


@dataclass
class Vacation:
        user_id: int
        start_date: date
        end_date: date
        vacation_id: Optional[int] = None


@dataclass
class Attestation:
        user_id: int
        start_date: date
        end_date: date
        cid: Optional[str] = None
        start_time: Optional[time] = None
        end_time: Optional[time] = None
        created_at: datetime = field(default_factory=datetime.now)
        attestation_id: Optional[int] = None

        @property
        def covers_full_day(self) -> bool:
                return self.start_time is None and self.end_time is None

        def covers(self, target_date: date) -> bool:
                return self.start_date <= target_date <= self.end_date


@dataclass
class Facultativo:
        start_date: date
        end_date: date
        description: str
        start_time: Optional[time] = None
        end_time: Optional[time] = None
        created_at: datetime = field(default_factory=datetime.now)
        facultativo_id: Optional[int] = None

        @property
        def covers_full_day(self) -> bool:
                return self.start_time is None and self.end_time is None

        def covers(self, target_date: date) -> bool:
                return self.start_date <= target_date <= self.end_date


@dataclass
class Notification:
        user_id: int
        message: str
        created_at: datetime
        is_read: bool = False
        notification_id: Optional[int] = None


# (flag, reviewed, approved, excused) attribute names for each anomaly stage.
_ANOMALY_STAGES = [
        ("arrival_late", "arrival_late_reviewed", "arrival_late_approved", "arrival_late_excused"),
        ("lunch_start_late", "lunch_start_late_reviewed", "lunch_start_late_approved", "lunch_start_late_excused"),
        ("lunch_end_late", "lunch_end_late_reviewed", "lunch_end_late_approved", "lunch_end_late_excused"),
        ("departure_early", "departure_early_reviewed", "departure_early_approved", "departure_early_excused"),
]


@dataclass
class DailyPonto:
        user_id: int
        entry_date: date
        arrival: Optional[time] = None
        lunch_start: Optional[time] = None
        lunch_end: Optional[time] = None
        departure: Optional[time] = None
        location_data: str = ""
        status: PontoStatus = PontoStatus.ON_TIME
        notes: Optional[str] = None
        manager_notes: Optional[str] = None
        has_lunch_break: bool = True
        ponto_id: Optional[int] = None
        excused_minutes: int = 0

        arrival_late: bool = False
        lunch_start_late: bool = False
        lunch_end_late: bool = False
        departure_early: bool = False

        arrival_late_reviewed: bool = False
        lunch_start_late_reviewed: bool = False
        lunch_end_late_reviewed: bool = False
        departure_early_reviewed: bool = False
        missing_reviewed: bool = False

        arrival_late_approved: bool = False
        lunch_start_late_approved: bool = False
        lunch_end_late_approved: bool = False
        departure_early_approved: bool = False
        missing_approved: bool = False

        arrival_late_excused: bool = False
        lunch_start_late_excused: bool = False
        lunch_end_late_excused: bool = False
        departure_early_excused: bool = False
        missing_excused: bool = False

        def get_placeholder(self, field: str, schedule: Optional[WorkSchedule]) -> Optional[time]:
                return _placeholder_time(field, self, schedule)

        @property
        def has_anomaly(self) -> bool:
                return _has_anomaly(self)

        @property
        def current_stage(self) -> str:
                return _current_stage(self)

        @property
        def worked_minutes(self) -> int:
                return _worked_minutes(self)

        def get_predicted_worked_minutes(self, schedule: WorkSchedule, use_expected: bool = True) -> int:
                arr, ls, le, dep = _predicted_times(self, schedule, use_expected)
                return _predicted_minutes(arr, ls, le, dep, schedule.has_lunch_break if schedule else self.has_lunch_break)

        @property
        def is_complete(self) -> bool:
                return _is_complete(self)

        @property
        def is_vacation(self) -> bool:
                return self.status == PontoStatus.DISMISSED and self.manager_notes == "Férias"

        @property
        def has_location(self) -> bool:
                return bool(re.search(r'-?\d+\.\d+\s*,\s*-?\d+\.\d+', self.location_data or ''))

        @property
        def status_label(self) -> str:
                """Display label; marks an unclosed past day as unknown unless a specific status was set."""
                return _status_label(self)


@dataclass
class CorrectionRequest:
        user_id: int
        ponto_date: date
        stage: str
        proposed_time: time
        status: str = "pending"
        created_at: datetime = field(default_factory=datetime.now)
        request_id: Optional[int] = None


@dataclass
class UserProfile:
        registration_number: Optional[str] = None
        cpf: Optional[str] = None
        department: Optional[str] = None
        position: Optional[str] = None
        secretariat: Optional[str] = None
        full_name: Optional[str] = None
        start_analysis_date: date = date(2026, 5, 1)
        birth_date: Optional[date] = None

        def is_complete(self) -> bool:
                return all([self.department, self.position, self.secretariat, self.full_name])


@dataclass
class AuditLog:
        user_id: int
        action: str
        target_id: Optional[int]
        timestamp: datetime
        details: Optional[str] = None
        log_id: Optional[int] = None


class User:
        def __init__(
                self,
                email,
                password_hash,
                role,
                user_id=None,
                profile=None,
                work_schedule=None,
                email_notifications_enabled=False,
        ):
                self.user_id = user_id
                self.email = email
                self.password_hash = password_hash
                self.role = role
                self.profile = profile or UserProfile()
                self.work_schedule = work_schedule
                self.email_notifications_enabled = email_notifications_enabled
                self.time_entries = []
                self.vacations = []
                self.attestations = []
                self.notifications = []

        @property
        def is_profile_complete(self) -> bool:
                return self.profile.is_complete()

        def is_on_vacation(self, target_date: date) -> bool:
                return _on_vacation(self.vacations, self.profile, target_date)

        def is_on_attestation(self, target_date: date) -> bool:
                return any(att.covers(target_date) for att in self.attestations)

        @property
        def is_manager(self) -> bool:
                return self.role in [UserRole.MANAGER, UserRole.ADMIN, UserRole.GESTOR]

        @property
        def is_gestor(self) -> bool:
                return self.role == UserRole.GESTOR

        @property
        def is_admin(self) -> bool:
                return self.role == UserRole.ADMIN

        @property
        def full_name(self) -> str:
                return self.profile.full_name if self.profile else ""

        @property
        def unread_notifications_count(self) -> int:
                return sum(1 for n in self.notifications if not n.is_read)

        @property
        def total_balance(self) -> int:
                return _total_balance(self)


def _find_member(enum_cls, value, transform):
        if not isinstance(value, str):
                return None
        lookup = {transform(member.value): member for member in enum_cls}
        return lookup.get(transform(value))


def _resolve_schedule_type(enum_cls, value):
        if not isinstance(value, str):
                return None
        if value.upper() == "12X36":
                return enum_cls.ROTATION_12X36
        return _find_member(enum_cls, value, str.upper)


def _is_work_day(schedule_type, rotation_start, target_date):
        if schedule_type == ScheduleType.STANDARD:
                return target_date.weekday() < 5
        if schedule_type == ScheduleType.ROTATION_12X36:
                return _is_rotation_work_day(rotation_start, target_date)
        return True


def _is_rotation_work_day(rotation_start, target_date):
        if not rotation_start:
                return True
        return (target_date - rotation_start).days % 2 == 0


def _daily_target(schedule, arrival, lunch_start, lunch_end, departure):
        if schedule.has_lunch_break:
                return minutes_between(arrival, lunch_start) + minutes_between(lunch_end, departure)
        return minutes_between(arrival, departure)


def _placeholder_time(field, ponto, schedule):
        if not schedule:
                return None
        if field == "lunch_start" and not ponto.lunch_start:
                return schedule.expected_lunch_start
        if field == "lunch_end" and not ponto.lunch_end:
                return schedule.expected_lunch_end
        if field == "departure" and not ponto.departure:
                return schedule.expected_departure
        return None


def _has_anomaly(ponto):
        if _missing_anomaly(ponto):
                return True
        for flag, reviewed, approved, excused in _ANOMALY_STAGES:
                if _stage_anomaly(ponto, flag, reviewed, approved, excused):
                        return True
        return False


def _missing_anomaly(ponto):
        if ponto.status == PontoStatus.MISSING and not (ponto.missing_reviewed or ponto.missing_approved or ponto.missing_excused):
                return True
        return False


def _stage_anomaly(ponto, flag, reviewed, approved, excused):
        if getattr(ponto, flag) and not (getattr(ponto, reviewed) or getattr(ponto, approved) or getattr(ponto, excused)):
                return True
        return False


def _current_stage(ponto):
        if not ponto.arrival:
                return "Chegada"
        if ponto.has_lunch_break and not ponto.lunch_start:
                return "Saída Almoço"
        if ponto.has_lunch_break and not ponto.lunch_end:
                return "Retorno Almoço"
        if not ponto.departure:
                return "Fim Jornada"
        return "Jornada Completa"


def _worked_minutes(ponto, has_lunch_break=None):
        if has_lunch_break is None:
                has_lunch_break = ponto.has_lunch_break
        if not has_lunch_break:
                return max(0, minutes_between(ponto.arrival, ponto.departure))
        morning = max(0, minutes_between(ponto.arrival, ponto.lunch_start)) if (ponto.arrival and ponto.lunch_start) else 0
        afternoon = max(0, minutes_between(ponto.lunch_end, ponto.departure)) if (ponto.lunch_end and ponto.departure) else 0
        return morning + afternoon


def _predicted_times(ponto, schedule, use_expected):
        if use_expected:
                return schedule.expected_arrival, schedule.expected_lunch_start, schedule.expected_lunch_end, schedule.expected_departure
        return (
                _fallback_time(ponto.arrival, schedule.expected_arrival),
                _fallback_time(ponto.lunch_start, schedule.expected_lunch_start),
                _fallback_time(ponto.lunch_end, schedule.expected_lunch_end),
                _fallback_time(ponto.departure, schedule.expected_departure),
        )


def _fallback_time(value, expected):
        return value or expected


def _predicted_minutes(arr, ls, le, dep, has_lunch_break):
        if not has_lunch_break:
                return minutes_between(arr, dep)
        return minutes_between(arr, ls) + minutes_between(le, dep)


def _is_complete(ponto):
        if ponto.has_lunch_break:
                return all([ponto.arrival, ponto.lunch_start, ponto.lunch_end, ponto.departure])
        return all([ponto.arrival, ponto.departure])


def _status_label(ponto):
        if ponto.status == PontoStatus.ON_TIME and not ponto.is_complete and ponto.entry_date < date.today():
                return "Desconhecido"
        return ponto.status.value


def _on_vacation(vacations, profile, target_date):
        if any(v.start_date <= target_date <= v.end_date for v in vacations):
                return True
        return _is_birthday_vacation(profile, target_date)


def _is_birthday_vacation(profile, target_date: date) -> bool:
        if not profile or not profile.birth_date:
                return False
        if profile.birth_date.month == target_date.month and profile.birth_date.day == target_date.day:
                return True
        return False


def _total_balance(user):
        if not user.work_schedule:
                return 0
        target = user.work_schedule.daily_target_minutes()
        return sum(_entry_balance(p, target, user.work_schedule) for p in _countable_entries(user, date.today()))


def _countable_entries(user, today):
        """Return time entries that contribute to the balance up to (but excluding) today."""
        analysis_start = user.profile.start_analysis_date if user.profile else None
        return [p for p in user.time_entries if _counts_toward_balance(p, analysis_start, user.work_schedule, today)]


def _counts_toward_balance(ponto, analysis_start, schedule, today: date) -> bool:
        if ponto.entry_date >= today:
                return False
        if analysis_start and ponto.entry_date < analysis_start:
                return False
        return schedule.is_work_day(ponto.entry_date)


def _entry_balance(ponto, target_minutes: int, schedule) -> int:
        if ponto.status in (PontoStatus.MISSING, PontoStatus.REJECTED):
                return _missing_balance(ponto, target_minutes)
        if ponto.status in (PontoStatus.DISMISSED, PontoStatus.JUSTIFIED):
                if ponto.excused_minutes:
                        return _worked_minutes_for_balance(ponto, schedule) + ponto.excused_minutes - target_minutes
                return 0
        return _worked_for_balance(ponto, schedule) - target_minutes


def _missing_balance(ponto, target_minutes):
        if ponto.status == PontoStatus.MISSING and (ponto.missing_approved or ponto.missing_excused):
                return 0
        return -target_minutes


def _worked_for_balance(ponto, schedule):
        if _has_approved_anomaly(ponto):
                return _neutralized_worked_minutes(ponto, schedule)
        return _worked_minutes_for_balance(ponto, schedule)


def _has_lunch_for_balance(ponto, schedule) -> bool:
        return schedule.has_lunch_break if schedule else ponto.has_lunch_break


def _worked_minutes_for_balance(ponto, schedule):
        return _worked_minutes(ponto, _has_lunch_for_balance(ponto, schedule))


def _neutralized_worked_minutes(ponto, schedule):
        arrival = _neutralized_time(ponto.arrival, schedule.expected_arrival, ponto.arrival_late_approved or ponto.arrival_late_excused)
        lunch_start = _neutralized_time(ponto.lunch_start, schedule.expected_lunch_start, (ponto.lunch_start_late_approved or ponto.lunch_start_late_excused) and schedule.expected_lunch_start is not None)
        lunch_end = _neutralized_time(ponto.lunch_end, schedule.expected_lunch_end, (ponto.lunch_end_late_approved or ponto.lunch_end_late_excused) and schedule.expected_lunch_end is not None)
        departure = _neutralized_time(ponto.departure, schedule.expected_departure, ponto.departure_early_approved or ponto.departure_early_excused)
        # A neutralized clock must never create an impossible timeline (e.g. a lunch
        # return earlier than the clocked lunch out); otherwise it fabricates hours.
        # Whenever a neutralization would break the order, fall back to the real clock.
        if lunch_start and arrival and lunch_start < arrival:
                lunch_start = ponto.lunch_start
        if lunch_end and lunch_start and lunch_end < lunch_start:
                lunch_end = ponto.lunch_end
        if departure and lunch_end and departure < lunch_end:
                departure = ponto.departure
        return _predicted_minutes(arrival, lunch_start, lunch_end, departure, _has_lunch_for_balance(ponto, schedule))


def _neutralized_time(actual, expected, neutralize):
        if neutralize:
                return expected
        return actual


def _has_approved_anomaly(ponto) -> bool:
        flags = [
                ponto.arrival_late_approved,
                ponto.lunch_start_late_approved,
                ponto.lunch_end_late_approved,
                ponto.departure_early_approved,
                ponto.arrival_late_excused,
                ponto.lunch_start_late_excused,
                ponto.lunch_end_late_excused,
                ponto.departure_early_excused,
        ]
        return any(flags)
