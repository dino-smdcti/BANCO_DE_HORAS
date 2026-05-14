from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from typing import List, Optional
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"

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
    start_analysis_date: date = date(2026, 1, 1)

@dataclass
class WorkSchedule:
    user_id: int
    expected_arrival: time
    expected_lunch_start: Optional[time]
    expected_lunch_end: Optional[time]
    expected_departure: time
    tolerance_minutes: int = 15
    has_lunch_break: bool = True
    schedule_id: Optional[int] = None

@dataclass
class JourneyType:
    name: str
    expected_arrival: time
    expected_lunch_start: Optional[time]
    expected_lunch_end: Optional[time]
    expected_departure: time
    tolerance_minutes: int = 15
    has_lunch_break: bool = True
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
    has_lunch_break: bool = True
    ponto_id: Optional[int] = None
    
    arrival_late: bool = False
    lunch_start_late: bool = False
    lunch_end_late: bool = False
    departure_early: bool = False

    arrival_late_approved: bool = False
    lunch_start_late_approved: bool = False
    lunch_end_late_approved: bool = False
    departure_early_approved: bool = False

    def get_placeholder(self, field: str, schedule: Optional[WorkSchedule]) -> Optional[time]:
        if not schedule: return None
        if field == "lunch_start" and not self.lunch_start: return schedule.expected_lunch_start
        if field == "lunch_end" and not self.lunch_end: return schedule.expected_lunch_end
        if field == "departure" and not self.departure: return schedule.expected_departure
        return None

    @property
    def has_anomaly(self) -> bool:
        # If an anomaly was approved, we don't count it as a pending anomaly for review
        # but we still want to know it happened.
        return any([
            self.arrival_late and not self.arrival_late_approved,
            self.lunch_start_late and not self.lunch_start_late_approved,
            self.lunch_end_late and not self.lunch_end_late_approved,
            self.departure_early and not self.departure_early_approved,
            self.status == PontoStatus.MISSING
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
        # New calculation rule: [LunchStart - Arrival] + [Departure - LunchEnd]
        if self.has_lunch_break:
            return self._delta(self.arrival, self.lunch_start) + self._delta(self.lunch_end, self.departure)
        
        # If no lunch break, continuous block from arrival to departure
        return self._delta(self.arrival, self.departure)

    def get_approved_bonus_minutes(self, schedule: WorkSchedule) -> int:
        bonus = 0
        if self.arrival_late_approved and self.arrival:
            # How many minutes did they lose?
            lost = self._delta(schedule.expected_arrival, self.arrival)
            if lost > 0: bonus += lost
        
        if self.lunch_start_late_approved and self.lunch_start:
            lost = self._delta(self.lunch_start, schedule.expected_lunch_start)
            if lost > 0: bonus += lost

        if self.lunch_end_late_approved and self.lunch_end:
            lost = self._delta(schedule.expected_lunch_end, self.lunch_end)
            if lost > 0: bonus += lost

        if self.departure_early_approved and self.departure:
            lost = self._delta(self.departure, schedule.expected_departure)
            if lost > 0: bonus += lost
            
        return bonus

    def get_predicted_worked_minutes(self, schedule: WorkSchedule) -> int:
        def delta(t1, t2):
            if not t1 or not t2: return 0
            return int((datetime.combine(date.min, t2) - datetime.combine(date.min, t1)).total_seconds() / 60)

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
        if not self.is_complete and self.entry_date < date.today():
            return "Desconhecido"
        return self.status.value

@dataclass
class CorrectionRequest:
    user_id: int
    ponto_date: date
    stage: str
    proposed_time: time
    justification: str
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
        for p in self.time_entries:
            if p.entry_date >= today: continue
            
            # Skip incomplete days unless they are explicitly marked as MISSING or REJECTED
            if not p.is_complete and p.status not in [PontoStatus.MISSING, PontoStatus.REJECTED]:
                continue

            if p.status == PontoStatus.MISSING or p.status == PontoStatus.REJECTED:
                balance -= target_minutes
            else:
                day_worked = p.worked_minutes + p.get_approved_bonus_minutes(self.work_schedule)
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
