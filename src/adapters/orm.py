from sqlalchemy import Table, Column, Integer, String, Date, Time, ForeignKey, Enum as SQLEnum, MetaData, Boolean, DateTime, Float
from sqlalchemy.orm import registry, relationship, composite
from src.domain.model import User, DailyPonto, UserProfile, UserRole, Vacation, Holiday, WorkSchedule, PontoStatus, JourneyType, Notification, AuditLog, CorrectionRequest, CompanySettings, ScheduleType
from datetime import datetime, date

metadata = MetaData()
mapper_registry = registry(metadata=metadata)

audit_logs = Table(
    "audit_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("action", String(255), nullable=False),
    Column("target_id", Integer, nullable=True),
    Column("timestamp", DateTime, default=datetime.now),
    Column("details", String, nullable=True),
)

journey_types = Table(
    "journey_types",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False, unique=True),
    Column("expected_arrival", Time, nullable=False),
    Column("expected_lunch_start", Time, nullable=True),
    Column("expected_lunch_end", Time, nullable=True),
    Column("expected_departure", Time, nullable=False),
    Column("tolerance_minutes", Integer, default=15),
    Column("has_lunch_break", Boolean, default=True),
    Column("schedule_type", SQLEnum(ScheduleType), default=ScheduleType.STANDARD),

)

work_schedules = Table(
    "work_schedules",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), unique=True, nullable=False),
    Column("expected_arrival", Time, nullable=False),
    Column("expected_lunch_start", Time, nullable=True),
    Column("expected_lunch_end", Time, nullable=True),
    Column("expected_departure", Time, nullable=False),
    Column("tolerance_minutes", Integer, default=15),
    Column("has_lunch_break", Boolean, default=True),
    Column("schedule_type", SQLEnum(ScheduleType), default=ScheduleType.STANDARD),

    Column("rotation_start_date", Date, nullable=True),
)

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(255), unique=True, nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("role", SQLEnum(UserRole), nullable=False),
    Column("registration_number", String(50), nullable=True),
    Column("cpf", String(14), nullable=True),
    Column("department", String(100), nullable=True),
    Column("position", String(100), nullable=True),
    Column("secretariat", String(100), nullable=True),
    Column("full_name", String(255), nullable=True),
    Column("email_notifications_enabled", Boolean, default=False),
    Column("start_analysis_date", Date, default=date(2026, 1, 1)),
)

daily_pontos = Table(
    "daily_pontos",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("entry_date", Date, nullable=False),
    Column("arrival", Time, nullable=True),
    Column("lunch_start", Time, nullable=True),
    Column("lunch_end", Time, nullable=True),
    Column("departure", Time, nullable=True),
    Column("location_data", String(1000), nullable=True),
    Column("status", SQLEnum(PontoStatus), default=PontoStatus.ON_TIME),
    Column("notes", String(1000), nullable=True),
    Column("manager_notes", String(1000), nullable=True),
    Column("has_lunch_break", Boolean, default=True),
    Column("arrival_late", Boolean, default=False),
    Column("lunch_start_late", Boolean, default=False),
    Column("lunch_end_late", Boolean, default=False),
    Column("departure_early", Boolean, default=False),
    Column("arrival_late_reviewed", Boolean, default=False),
    Column("lunch_start_late_reviewed", Boolean, default=False),
    Column("lunch_end_late_reviewed", Boolean, default=False),
    Column("departure_early_reviewed", Boolean, default=False),
    Column("missing_reviewed", Boolean, default=False),

    Column("arrival_late_approved", Boolean, default=False),
    Column("lunch_start_late_approved", Boolean, default=False),
    Column("lunch_end_late_approved", Boolean, default=False),
    Column("departure_early_approved", Boolean, default=False),
    Column("missing_approved", Boolean, default=False),

    Column("arrival_late_excused", Boolean, default=False),
    Column("lunch_start_late_excused", Boolean, default=False),
    Column("lunch_end_late_excused", Boolean, default=False),
    Column("departure_early_excused", Boolean, default=False),
    Column("missing_excused", Boolean, default=False),
)

correction_requests = Table(
    "correction_requests",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("ponto_date", Date, nullable=False),
    Column("stage", String(50), nullable=False),
    Column("proposed_time", Time, nullable=False),
    Column("status", String(20), default="pending"),
    Column("created_at", DateTime, default=datetime.now),
)

vacations = Table(
    "vacations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date, nullable=False),
)

holidays = Table(
    "holidays",
    metadata,
    Column("holiday_date", Date, primary_key=True),
    Column("description", String(255), nullable=False),
    Column("is_mandatory", Boolean, default=True),
)

company_settings = Table(
    "company_settings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("lat", Float, nullable=False),
    Column("lon", Float, nullable=False),
    Column("start_analysis_date", Date, nullable=False, default=date(2026, 1, 1)),
)

notifications = Table(
    "notifications",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("message", String(500), nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("is_read", Boolean, default=False),
)

def start_mappers():
    if hasattr(User, "__mapper__") or hasattr(CompanySettings, "__mapper__"):
        return

    mapper_registry.map_imperatively(CompanySettings, company_settings)

    mapper_registry.map_imperatively(
        User,
        users,
        properties={
            "user_id": users.c.id,
            "profile": composite(
                UserProfile,
                users.c.registration_number,
                users.c.cpf,
                users.c.department,
                users.c.position,
                users.c.secretariat,
                users.c.full_name,
                users.c.start_analysis_date,
            ),
            "time_entries": relationship(DailyPonto, backref="user", order_by=daily_pontos.c.entry_date, cascade="all, delete-orphan"),
            "vacations": relationship(Vacation, backref="user", cascade="all, delete-orphan"),
            "work_schedule": relationship(WorkSchedule, backref="user", uselist=False, cascade="all, delete-orphan"),
            "notifications": relationship(Notification, backref="user", order_by=notifications.c.created_at.desc(), cascade="all, delete-orphan")
        }
    )

    mapper_registry.map_imperatively(
        WorkSchedule,
        work_schedules,
        properties={
            "schedule_id": work_schedules.c.id,
        }
    )

    mapper_registry.map_imperatively(
        DailyPonto,
        daily_pontos,
        properties={
            "ponto_id": daily_pontos.c.id,
        }
    )

    mapper_registry.map_imperatively(
        CorrectionRequest,
        correction_requests,
        properties={
            "request_id": correction_requests.c.id,
        }
    )

    mapper_registry.map_imperatively(
        Vacation,
        vacations,
        properties={
            "vacation_id": vacations.c.id,
        }
    )

    mapper_registry.map_imperatively(
        Notification,
        notifications,
        properties={
            "notification_id": notifications.c.id,
        }
    )

    mapper_registry.map_imperatively(Holiday, holidays)
    
    mapper_registry.map_imperatively(
        JourneyType,
        journey_types,
        properties={
            "journey_id": journey_types.c.id,
        }
    )

    mapper_registry.map_imperatively(
        AuditLog,
        audit_logs,
        properties={
            "log_id": audit_logs.c.id,
        }
    )

