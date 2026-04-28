from sqlalchemy import Table, Column, Integer, String, Date, Time, ForeignKey, Enum as SQLEnum, MetaData, Boolean
from sqlalchemy.orm import registry, relationship, composite
from src.domain.model import User, DailyPonto, UserProfile, UserRole, Vacation, Holiday

metadata = MetaData()
mapper_registry = registry(metadata=metadata)

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

def start_mappers():
    if User in mapper_registry.mappers:
        return

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
            ),
            "time_entries": relationship(DailyPonto, backref="user", order_by=daily_pontos.c.entry_date),
            "vacations": relationship(Vacation, backref="user")
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
        Vacation,
        vacations,
        properties={
            "vacation_id": vacations.c.id,
        }
    )

    mapper_registry.map_imperatively(Holiday, holidays)
