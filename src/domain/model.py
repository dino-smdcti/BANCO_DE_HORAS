from dataclasses import dataclass
from datetime import datetime, date, time
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

@dataclass
class WorkSchedule:
    user_id: int
    expected_arrival: time
    expected_lunch_start: time
    expected_lunch_end: time
    expected_departure: time
    tolerance_minutes: int = 15
    schedule_id: Optional[int] = None

@dataclass
class JourneyType:
    name: str
    expected_arrival: time
    expected_lunch_start: time
    expected_lunch_end: time
    expected_departure: time
    tolerance_minutes: int = 15
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
    ponto_id: Optional[int] = None
    
    # Flags for lateness/deviations
    arrival_late: bool = False
    lunch_start_late: bool = False
    lunch_end_late: bool = False
    departure_early: bool = False

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
        if not self.lunch_start: return "Saída Almoço"
        if not self.lunch_end: return "Retorno Almoço"
        if not self.departure: return "Fim Jornada"
        return "Jornada Completa"

    @property
    def worked_minutes(self) -> int:
        def delta(t1, t2):
            if not t1 or not t2: return 0
            return int((datetime.combine(date.min, t2) - datetime.combine(date.min, t1)).total_seconds() / 60)
        
        morning = delta(self.arrival, self.lunch_start)
        afternoon = delta(self.lunch_end, self.departure)
        return morning + afternoon

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
        if not self.work_schedule:
            return 0
        
        def delta(t1, t2):
            return int((datetime.combine(date.min, t2) - datetime.combine(date.min, t1)).total_seconds() / 60)
        
        expected_daily = (delta(self.work_schedule.expected_arrival, self.work_schedule.expected_lunch_start) + 
                          delta(self.work_schedule.expected_lunch_end, self.work_schedule.expected_departure))
        
        # Calculate balance for worked entries vs expected
        balance = 0
        for p in self.time_entries:
            # Skip entries not fully worked (unless missing/justified)
            if p.status == PontoStatus.MISSING:
                balance -= expected_daily
            elif p.status == PontoStatus.JUSTIFIED:
                continue # Assuming full credit
            else:
                balance += (p.worked_minutes - expected_daily)
        return balance
