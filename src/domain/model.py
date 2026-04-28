from dataclasses import dataclass
from datetime import datetime, date, time
from typing import List, Optional
from enum import Enum

class UserRole(str, Enum):
    MANAGER = "manager"
    EMPLOYEE = "employee"

@dataclass(frozen=True)
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
class DailyPonto:
    user_id: int
    entry_date: date
    arrival: Optional[time] = None
    lunch_start: Optional[time] = None
    lunch_end: Optional[time] = None
    departure: Optional[time] = None
    location_data: str = "" # Formato: "Chegada: ... | Almoço: ..."
    ponto_id: Optional[int] = None

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

@dataclass(frozen=True)
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

class User:
    def __init__(
        self, 
        email: str, 
        password_hash: str, 
        role: UserRole,
        user_id: Optional[int] = None,
        profile: Optional[UserProfile] = None
    ):
        self.user_id = user_id
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.profile = profile or UserProfile()
        self.time_entries: List[DailyPonto] = []
        self.vacations: List[Vacation] = []

    @property
    def is_profile_complete(self) -> bool:
        return self.profile.is_complete()
    
    @property
    def is_manager(self) -> bool:
        return self.role == UserRole.MANAGER
