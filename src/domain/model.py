from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from typing import List, Optional
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"

class ScheduleType(str, Enum):
    STANDARD = "STANDARD"
    ROTATION_12X36 = "ROTATION_12X36"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            normalized = value.upper()
            if normalized == "12X36":
                return cls.ROTATION_12X36
            for member in cls:
                if member.value == normalized:
                    return member
        return None

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
        if self.schedule_type == ScheduleType.STANDARD:
            return target_date.weekday() < 5
        if self.schedule_type == ScheduleType.ROTATION_12X36:
            if not self.rotation_start_date: return True
            diff = (target_date - self.rotation_start_date).days
            return diff % 2 == 0
        return True

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
class Notification:
    user_id: int
    message: str
    created_at: datetime
    is_read: bool = False
    notification_id: Optional[int] = None

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
        if not schedule: return None
        if field == "lunch_start" and not self.lunch_start: return schedule.expected_lunch_start
        if field == "lunch_end" and not self.lunch_end: return schedule.expected_lunch_end
        if field == "departure" and not self.departure: return schedule.expected_departure
        return None

    @property
    def has_anomaly(self) -> bool:
        # An anomaly is pending if it exists and hasn't been reviewed, approved, or excused.
        return any([
            self.arrival_late and not (self.arrival_late_reviewed or self.arrival_late_approved or self.arrival_late_excused),
            self.lunch_start_late and not (self.lunch_start_late_reviewed or self.lunch_start_late_approved or self.lunch_start_late_excused),
            self.lunch_end_late and not (self.lunch_end_late_reviewed or self.lunch_end_late_approved or self.lunch_end_late_excused),
            self.departure_early and not (self.departure_early_reviewed or self.departure_early_approved or self.departure_early_excused),
            self.status == PontoStatus.MISSING and not (self.missing_reviewed or self.missing_approved or self.missing_excused)
        ])

    @property
    def current_stage(self) -> str:
        if not self.arrival: return "Chegada"
        if self.has_lunch_break:
            if not self.lunch_start: return "Saída Almoço"
            if not self.lunch_end: return "Retorno Almoço"
        if not self.departure: return "Fim Jornada"
        return "Jornada Completa"

    def _delta(self, t1, t2):
        if not t1 or not t2: return 0
        d1 = datetime.combine(date.min, t1)
        d2 = datetime.combine(date.min, t2)
        return int((d2 - d1).total_seconds() / 60)

    @property
    def worked_minutes(self) -> int:
        if self.has_lunch_break:
            # If the user has a lunch break, but the lunch times are missing, 
            # treat it as a continuous block to avoid returning 0.
            if not self.lunch_start or not self.lunch_end:
                 return max(0, self._delta(self.arrival, self.departure))
            return self._delta(self.arrival, self.lunch_start) + self._delta(self.lunch_end, self.departure)
        
        # If no lunch break, continuous block from arrival to departure
        return max(0, self._delta(self.arrival, self.departure))

    def get_approved_bonus_minutes(self, schedule: WorkSchedule) -> int:
        # Bonuses should represent extra time worked, not compensation for late arrival.
        # Late arrivals are not "bonus", they are "authorized absence". 
        # Authorized absences should simply ignore the penalty, not provide a positive bonus.
        
        # If the user worked overtime (more than target), that could be a bonus.
        # But this function seems to be used to *offset* the 'target_minutes' penalty.
        # If I just return 0 here, 'late arrival approved' will still mean (day_worked - target_minutes)
        # where day_worked is lower than target.
        # The goal is likely: if late is approved, don't penalize.
        return 0

    def get_predicted_worked_minutes(self, schedule: WorkSchedule, use_expected: bool = True) -> int:
        def delta(t1, t2):
            if not t1 or not t2: return 0
            return int((datetime.combine(date.min, t2) - datetime.combine(date.min, t1)).total_seconds() / 60)

        if use_expected:
            arr, ls, le, dep = schedule.expected_arrival, schedule.expected_lunch_start, schedule.expected_lunch_end, schedule.expected_departure
        else:
            arr = self.arrival or schedule.expected_arrival
            ls = self.lunch_start or schedule.expected_lunch_start
            le = self.lunch_end or schedule.expected_lunch_end
            dep = self.departure or schedule.expected_departure

        if not self.has_lunch_break:
            return delta(arr, dep)

        morning = delta(arr, ls)
        afternoon = delta(le, dep)
        return morning + afternoon

    @property
    def is_complete(self) -> bool:
        if self.has_lunch_break:
            return all([self.arrival, self.lunch_start, self.lunch_end, self.departure])
        return all([self.arrival, self.departure])

    @property
    def status_label(self) -> str:
        """
        Returns the display label for the status. 
        Only returns 'Desconhecido' if the day has passed, it's not complete, and no specific status (like MISSING) was set.
        """
        if self.status == PontoStatus.ON_TIME and not self.is_complete and self.entry_date < date.today():
            return "Desconhecido"
        return self.status.value

@dataclass
class CorrectionRequest:
    user_id: int
    ponto_date: date
    stage: str
    proposed_time: time
    status: str = "pending"
    created_at: datetime = datetime.now()
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

    def is_complete(self) -> bool:
        return all([self.registration_number, self.cpf, self.department, self.position, self.secretariat, self.full_name])

@dataclass
class AuditLog:
    user_id: int
    action: str
    target_id: Optional[int]
    timestamp: datetime
    details: Optional[str] = None
    log_id: Optional[int] = None

class User:
    def __init__(self, email, password_hash, role, user_id=None, profile=None, work_schedule=None, email_notifications_enabled=False):
        self.user_id = user_id
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.profile = profile or UserProfile()
        self.work_schedule = work_schedule
        self.email_notifications_enabled = email_notifications_enabled
        self.time_entries = []
        self.vacations = []
        self.notifications = []

    @property
    def is_profile_complete(self) -> bool:
        return self.profile.is_complete()

    @property
    def is_manager(self) -> bool:
        return self.role in [UserRole.MANAGER, UserRole.ADMIN]

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def unread_notifications_count(self) -> int:
        return sum(1 for n in self.notifications if not n.is_read)

    @property
    def total_balance(self) -> int:
        if not self.work_schedule: return 0

        def delta(t1, t2):
            if not t1 or not t2: return 0
            d1 = datetime.combine(date.min, t1)
            d2 = datetime.combine(date.min, t2)
            return int((d2 - d1).total_seconds() / 60)

        # Calculate daily target
        if self.work_schedule.has_lunch_break:
            target_minutes = (delta(self.work_schedule.expected_arrival, self.work_schedule.expected_lunch_start) + 
                              delta(self.work_schedule.expected_lunch_end, self.work_schedule.expected_departure))
        else:
            target_minutes = delta(self.work_schedule.expected_arrival, self.work_schedule.expected_departure)

        balance = 0
        today = date.today()
        
        # We need to consider all days up to today.
        for p in self.time_entries:
            if p.entry_date >= today: continue
            
            # Skip entries before start_analysis_date
            if self.profile and self.profile.start_analysis_date and p.entry_date < self.profile.start_analysis_date:
                continue
            
            # Check if it was a work day for this user
            if not self.work_schedule.is_work_day(p.entry_date): continue

            # If the log is missing or rejected, full penalty unless excused/approved.
            if p.status == PontoStatus.MISSING or p.status == PontoStatus.REJECTED:
                if p.status == PontoStatus.MISSING and (p.missing_approved or p.missing_excused):
                    continue
                balance -= target_minutes
                continue

            # If dismissed or justified, no penalty (target met)
            if p.status == PontoStatus.DISMISSED or p.status == PontoStatus.JUSTIFIED:
                continue

            # For all other statuses (ON_TIME, LATE, CORRECTED), calculate worked time.
            # If there are approved OR excused anomalies, use predicted worked minutes based on schedule
            excused_conditions = [
                p.arrival_late_approved, p.lunch_start_late_approved, p.lunch_end_late_approved, p.departure_early_approved,
                p.arrival_late_excused, p.lunch_start_late_excused, p.lunch_end_late_excused, p.departure_early_excused
            ]
            if any(excused_conditions):
                 day_worked = p.get_predicted_worked_minutes(self.work_schedule)
            else:
                 day_worked = p.worked_minutes
            
            balance += (day_worked - target_minutes)
        return balance

    @property
    def today_balance(self) -> int:
        if not self.work_schedule: return 0

        def delta(t1, t2):
            if not t1 or not t2: return 0
            d1 = datetime.combine(date.min, t1)
            d2 = datetime.combine(date.min, t2)
            return int((d2 - d1).total_seconds() / 60)

        # Calculate daily target
        if self.work_schedule.has_lunch_break:
            target_minutes = (delta(self.work_schedule.expected_arrival, self.work_schedule.expected_lunch_start) + 
                              delta(self.work_schedule.expected_lunch_end, self.work_schedule.expected_departure))
        else:
            target_minutes = delta(self.work_schedule.expected_arrival, self.work_schedule.expected_departure)

        today = date.today()
        # Find today's entry
        p = next((p for p in self.time_entries if p.entry_date == today), None)
        if not p or not p.is_complete: return 0
        
        day_worked = p.worked_minutes + p.get_approved_bonus_minutes(self.work_schedule)
        return day_worked - target_minutes
