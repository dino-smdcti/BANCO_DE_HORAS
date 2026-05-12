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
    is_mandatory: bool = True  # True = Feriado, False = Ponto Facultativo

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
    location_data: str = "" # Formato: "Chegada: ... | Almoço: ..."
    status: PontoStatus = PontoStatus.ON_TIME
    justification: Optional[str] = None
    notes: Optional[str] = None
    has_lunch_break: bool = True
    ponto_id: Optional[int] = None
    
    # Flags for lateness/deviations
    arrival_late: bool = False
    lunch_start_late: bool = False
    lunch_end_late: bool = False
    departure_early: bool = False

    def get_placeholder(self, field: str, schedule: Optional[WorkSchedule]) -> Optional[time]:
        if not schedule: return None
        if field == "lunch_start" and not self.lunch_start: return schedule.expected_lunch_start
        if field == "lunch_end" and not self.lunch_end: return schedule.expected_lunch_end
        if field == "departure" and not self.departure: return schedule.expected_departure
        return None

    @property
    def has_anomaly(self) -> bool:
        return any([
            self.arrival_late,
            self.lunch_start_late,
            self.lunch_end_late,
            self.departure_early,
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

    @property
    def worked_minutes(self) -> int:
        def delta(t1, t2):
            if not t1 or not t2: return 0
            d1 = datetime.combine(date.min, t1)
            d2 = datetime.combine(date.min, t2)
            return int((d2 - d1).total_seconds() / 60)
        
        # Total duration from Arrival to Departure
        total_span = delta(self.arrival, self.departure)
        
        # Calculate break duration
        break_duration = delta(self.lunch_start, self.lunch_end)
        
        if self.has_lunch_break:
            return total_span - break_duration
        
        return total_span

    def get_predicted_worked_minutes(self, schedule: WorkSchedule) -> int:
        def delta(t1, t2):
            if not t1 or not t2: return 0
            return int((datetime.combine(date.min, t2) - datetime.combine(date.min, t1)).total_seconds() / 60)

        # Use actuals if available, otherwise use scheduled times
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
    stage: str  # 'arrival', 'lunch_start', 'lunch_end', 'departure'
    proposed_time: time
    justification: str
    status: str = "pending"  # "pending", "approved", "rejected"
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
        return all([
            self.registration_number,
            self.cpf,
            self.department,
            self.position,
            self.secretariat,
            self.full_name
        ])

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
        email: str, 
        password_hash: str, 
        role: UserRole,
        user_id: Optional[int] = None,
        profile: Optional[UserProfile] = None,
        work_schedule: Optional[WorkSchedule] = None,
        email_notifications_enabled: bool = False
    ):
        self.user_id = user_id
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.profile = profile or UserProfile()
        self.work_schedule = work_schedule
        self.email_notifications_enabled = email_notifications_enabled
        self.time_entries: List[DailyPonto] = []
        self.vacations: List[Vacation] = []
        self.notifications: List[Notification] = []

    @property
    def is_profile_complete(self) -> bool:
        return self.profile.is_complete()
    
    @property
    def is_manager(self) -> bool:
        return self.role == UserRole.MANAGER

    @property
    def unread_notifications_count(self) -> int:
        return sum(1 for n in self.notifications if not n.is_read)

    @property
    def total_balance(self) -> int:
        if not self.work_schedule: return 0

        def delta(t1, t2):
            if not t1 or not t2: return 0
            return int((datetime.combine(date.min, t2) - datetime.combine(date.min, t1)).total_seconds() / 60)

        # Calculate daily target dynamically
        if self.work_schedule.has_lunch_break:
            target_minutes = (delta(self.work_schedule.expected_arrival, self.work_schedule.expected_lunch_start) + 
                              delta(self.work_schedule.expected_lunch_end, self.work_schedule.expected_departure))
        else:
            target_minutes = delta(self.work_schedule.expected_arrival, self.work_schedule.expected_departure)

        balance = 0
        today = date.today()
        
        for p in self.time_entries:
            # Exclude today from historical balance
            if p.entry_date >= today:
                continue
                
            # If entry is missing or rejected, debit the target.
            if p.status == PontoStatus.MISSING or p.status == PontoStatus.REJECTED:
                balance -= target_minutes
            elif p.is_complete:
                # Credit actual work (could be less than target, which results in a net debit for that day)
                balance += (p.worked_minutes - target_minutes)
            else:
                # Incomplete day (without missing/rejected flag) - debit the target to prevent undercounting
                balance -= target_minutes

        return balance

