from sqlalchemy import Table, Column, Integer, String, Date, Time, ForeignKey, Enum as SQLEnum, MetaData, Boolean, DateTime, Float, UniqueConstraint, Index, Text
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import registry, relationship, composite
from datetime import datetime, date
from src.domain.model import User, DailyPonto, UserProfile, UserRole, Vacation, Holiday, WorkSchedule, PontoStatus, JourneyType, Notification, AuditLog, CorrectionRequest, CompanySettings, ScheduleType, Attestation, Facultativo, AuthToken, AbsenceState, RateLimitEntry, Team, TeamTask, TaskChecklistItem, Accomplishment, Idea, IdeaVote, S5Audit, S5Item, WikiArticle, Mentorship, Kudos, TeamEvent
from src.config import (
        ATTESTATION_CID_COLUMN_LENGTH,
        AUDIT_ACTION_COLUMN_LENGTH,
        CORRECTION_STAGE_COLUMN_LENGTH,
        CORRECTION_STATUS_COLUMN_LENGTH,
        CORRECTION_STATUS_PENDING,
        CPF_COLUMN_LENGTH,
        DEFAULT_ANALYSIS_START_DATE,
        DEFAULT_TOLERANCE_MINUTES,
        DEPARTMENT_COLUMN_LENGTH,
        EMAIL_COLUMN_LENGTH,
        FACULTATIVO_DESCRIPTION_COLUMN_LENGTH,
        FULL_NAME_COLUMN_LENGTH,
        HOLIDAY_DESCRIPTION_COLUMN_LENGTH,
        LOCATION_DATA_COLUMN_LENGTH,
        MANAGER_NOTES_COLUMN_LENGTH,
        NAME_COLUMN_LENGTH,
        NOTES_COLUMN_LENGTH,
        NOTIFICATION_MESSAGE_COLUMN_LENGTH,
        PASSWORD_COLUMN_LENGTH,
        POSITION_COLUMN_LENGTH,
        REGISTRATION_NUMBER_COLUMN_LENGTH,
        ROLE_COLUMN_LENGTH,
        RATE_LIMIT_BUCKET_COLUMN_LENGTH,
        SECRETARIAT_COLUMN_LENGTH,
        TOKEN_HASH_COLUMN_LENGTH,
        TOKEN_KIND_COLUMN_LENGTH,
)

class UserRoleType(TypeDecorator):
    """SQLAlchemy type to store UserRole as lowercase string and load case-insensitively."""
    impl = String(ROLE_COLUMN_LENGTH)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        val_str = value.value if isinstance(value, UserRole) else str(value)
        # PostgreSQL enum 'userrole' has values: ADMIN, MANAGER, EMPLOYEE, gestor
        val_lower = val_str.lower()
        if val_lower in ("admin", "manager", "employee"):
            return val_lower.upper()
        if val_lower in ("gestor",):
            return "gestor"
        return val_str

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return UserRole(value)
        except Exception:
            return UserRole(value.lower())


metadata = MetaData()
mapper_registry = registry(metadata=metadata)

teams = Table(
    "teams",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(NAME_COLUMN_LENGTH), unique=True, nullable=False),
    Column("secretariat", String(SECRETARIAT_COLUMN_LENGTH), nullable=True),
    Column("lead_user_id", Integer, ForeignKey("users.id"), nullable=True),
)

team_tasks = Table(
    "team_tasks",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("team_id", Integer, ForeignKey("teams.id"), nullable=False),
    Column("title", String(NAME_COLUMN_LENGTH), nullable=False),
    Column("description", String(NOTES_COLUMN_LENGTH), nullable=True),
    Column("assignee_id", Integer, ForeignKey("users.id"), nullable=True),
    Column("due_date", Date, nullable=True),
    Column("status", String(CORRECTION_STATUS_COLUMN_LENGTH), default="todo", nullable=False),
    Column("created_by", Integer, ForeignKey("users.id"), nullable=True),
    Column("created_at", DateTime, default=datetime.now, nullable=False),
)

task_checklist_items = Table(
    "task_checklist_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("task_id", Integer, ForeignKey("team_tasks.id"), nullable=False),
    Column("label", String(NAME_COLUMN_LENGTH), nullable=False),
    Column("done", Boolean, default=False, nullable=False),
)

accomplishments = Table(
    "accomplishments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("team_id", Integer, ForeignKey("teams.id"), nullable=False),
    Column("title", String(NAME_COLUMN_LENGTH), nullable=False),
    Column("description", String(NOTES_COLUMN_LENGTH), nullable=True),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date, nullable=True),
    Column("achieved_by_user_id", Integer, ForeignKey("users.id"), nullable=True),
    Column("created_by", Integer, ForeignKey("users.id"), nullable=True),
    Column("created_at", DateTime, default=datetime.now, nullable=False),
)

ideas = Table(
    "ideas",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("team_id", Integer, ForeignKey("teams.id"), nullable=False),
    Column("title", String(NAME_COLUMN_LENGTH), nullable=False),
    Column("author_user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("category", String(32), default="idea", nullable=False),
    Column("description", String(NOTES_COLUMN_LENGTH), nullable=True),
    Column("status", String(32), default="open", nullable=False),
    Column("review_date", Date, nullable=True),
    Column("review_owner", String(NAME_COLUMN_LENGTH), nullable=True),
    Column("created_at", DateTime, default=datetime.now, nullable=False),
)

idea_votes = Table(
    "idea_votes",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("idea_id", Integer, ForeignKey("ideas.id"), nullable=False),
    Column("voter_user_id", Integer, ForeignKey("users.id"), nullable=False),
    UniqueConstraint("idea_id", "voter_user_id", name="unique_idea_voter"),
)

s5_audits = Table(
    "s5_audits",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("team_id", Integer, ForeignKey("teams.id"), nullable=False),
    Column("date", Date, nullable=False),
    Column("auditor_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("score", Float, default=0.0, nullable=False),
    Column("notes", String(NOTES_COLUMN_LENGTH), nullable=True),
)

s5_items = Table(
    "s5_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("s5_audit_id", Integer, ForeignKey("s5_audits.id"), nullable=False),
    Column("label", String(NAME_COLUMN_LENGTH), nullable=False),
    Column("passed", Boolean, default=False, nullable=False),
)

wiki_articles = Table(
    "wiki_articles",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("team_id", Integer, ForeignKey("teams.id"), nullable=True),
    Column("author_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("title", String(NAME_COLUMN_LENGTH), nullable=False),
    Column("body", Text, nullable=False),
    Column("updated_at", DateTime, default=datetime.now, nullable=False),
)

mentorships = Table(
    "mentorships",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("team_id", Integer, ForeignKey("teams.id"), nullable=False),
    Column("mentor_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("mentee_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("start_date", Date, nullable=False),
    Column("active", Boolean, default=True, nullable=False),
)

kudos = Table(
    "kudos",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("team_id", Integer, ForeignKey("teams.id"), nullable=False),
    Column("giver_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("receiver_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("message", String(NOTES_COLUMN_LENGTH), nullable=False),
    Column("created_at", DateTime, default=datetime.now, nullable=False),
)

team_events = Table(
    "team_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("team_id", Integer, ForeignKey("teams.id"), nullable=False),
    Column("title", String(NAME_COLUMN_LENGTH), nullable=False),
    Column("date", Date, nullable=False),
    Column("description", String(NOTES_COLUMN_LENGTH), nullable=True),
    Column("created_at", DateTime, default=datetime.now, nullable=False),
)

audit_logs = Table(
    "audit_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("action", String(AUDIT_ACTION_COLUMN_LENGTH), nullable=False),
    Column("target_id", Integer, nullable=True),
    Column("timestamp", DateTime, default=datetime.now),
    Column("details", String, nullable=True),
)

journey_types = Table(
    "journey_types",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(NAME_COLUMN_LENGTH), nullable=False, unique=True),
    Column("expected_arrival", Time, nullable=False),
    Column("expected_lunch_start", Time, nullable=True),
    Column("expected_lunch_end", Time, nullable=True),
    Column("expected_departure", Time, nullable=False),
    Column("tolerance_minutes", Integer, default=DEFAULT_TOLERANCE_MINUTES),
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
    Column("tolerance_minutes", Integer, default=DEFAULT_TOLERANCE_MINUTES),
    Column("has_lunch_break", Boolean, default=True),
    Column("schedule_type", SQLEnum(ScheduleType), default=ScheduleType.STANDARD),
    Column("rotation_start_date", Date, nullable=True),
)

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(EMAIL_COLUMN_LENGTH), unique=True, nullable=False),
    Column("password_hash", String(PASSWORD_COLUMN_LENGTH), nullable=False),
    Column("role", UserRoleType(), nullable=False),
    Column("registration_number", String(REGISTRATION_NUMBER_COLUMN_LENGTH), nullable=True),
    Column("cpf", String(CPF_COLUMN_LENGTH), nullable=True),
    Column("department", String(DEPARTMENT_COLUMN_LENGTH), nullable=True),
    Column("position", String(POSITION_COLUMN_LENGTH), nullable=True),
    Column("secretariat", String(SECRETARIAT_COLUMN_LENGTH), nullable=True),
    Column("full_name", String(FULL_NAME_COLUMN_LENGTH), nullable=True),
    Column("email_notifications_enabled", Boolean, default=False),
    Column("password_set", Boolean, default=False, nullable=False),
    Column("start_analysis_date", Date, default=DEFAULT_ANALYSIS_START_DATE),
    Column("birth_date", Date, nullable=True),
    Column("team_id", Integer, ForeignKey("teams.id"), nullable=True),
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
    Column("location_data", String(LOCATION_DATA_COLUMN_LENGTH), nullable=True),
    Column("status", SQLEnum(PontoStatus), default=PontoStatus.ON_TIME),
    Column("notes", String(NOTES_COLUMN_LENGTH), nullable=True),
    Column("manager_notes", String(MANAGER_NOTES_COLUMN_LENGTH), nullable=True),
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
    Column("lunch_start_early", Boolean, default=False),
    Column("lunch_start_early_reviewed", Boolean, default=False),
    Column("lunch_start_early_approved", Boolean, default=False),
    Column("lunch_start_early_excused", Boolean, default=False),
    Column("excused_minutes", Integer, default=0),
    UniqueConstraint("user_id", "entry_date", name="unique_user_entry_date"),
)

correction_requests = Table(
    "correction_requests",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("ponto_date", Date, nullable=False),
    Column("stage", String(CORRECTION_STAGE_COLUMN_LENGTH), nullable=False),
    Column("proposed_time", Time, nullable=False),
    Column("status", String(CORRECTION_STATUS_COLUMN_LENGTH), default=CORRECTION_STATUS_PENDING),
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

attestations = Table(
    "attestations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date, nullable=False),
    Column("cid", String(ATTESTATION_CID_COLUMN_LENGTH), nullable=True),
    Column("start_time", Time, nullable=True),
    Column("end_time", Time, nullable=True),
    Column("created_at", DateTime, default=datetime.now),
)

facultativos = Table(
    "facultativos",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date, nullable=False),
    Column("description", String(FACULTATIVO_DESCRIPTION_COLUMN_LENGTH), nullable=True),
    Column("start_time", Time, nullable=True),
    Column("end_time", Time, nullable=True),
    Column("created_at", DateTime, default=datetime.now),
)

holidays = Table(
    "holidays",
    metadata,
    Column("holiday_date", Date, primary_key=True),
    Column("description", String(HOLIDAY_DESCRIPTION_COLUMN_LENGTH), nullable=False),
    Column("is_mandatory", Boolean, default=True),
)

company_settings = Table(
    "company_settings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("lat", Float, nullable=False),
    Column("lon", Float, nullable=False),
    Column("start_analysis_date", Date, nullable=False, default=DEFAULT_ANALYSIS_START_DATE),
)

notifications = Table(
    "notifications",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("message", String(NOTIFICATION_MESSAGE_COLUMN_LENGTH), nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("is_read", Boolean, default=False),
)

auth_tokens = Table(
    "auth_tokens",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("token_hash", String(TOKEN_HASH_COLUMN_LENGTH), unique=True, nullable=False),
    Column("kind", String(TOKEN_KIND_COLUMN_LENGTH), nullable=False),
    Column("expires_at", DateTime, nullable=False),
    Column("used", Boolean, default=False),
    Column("created_at", DateTime, default=datetime.now),
)

rate_limit_entries = Table(
    "rate_limit_entries",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("bucket", String(RATE_LIMIT_BUCKET_COLUMN_LENGTH), nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.now),
)
Index("ix_rate_limit_bucket_created", rate_limit_entries.c.bucket, rate_limit_entries.c.created_at)


absence_state = Table(
    "absence_state",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("last_check_date", Date, nullable=True),
    Column("updated_at", DateTime, default=datetime.now),
)


Index("ix_daily_pontos_entry_date", daily_pontos.c.entry_date)
Index("ix_daily_pontos_user_entry_date", daily_pontos.c.user_id, daily_pontos.c.entry_date)
Index("ix_audit_logs_user_id", audit_logs.c.user_id)
Index("ix_audit_logs_timestamp", audit_logs.c.timestamp)
Index("ix_notifications_user_created", notifications.c.user_id, notifications.c.created_at)
Index("ix_correction_requests_status", correction_requests.c.status)
Index("ix_vacations_user_dates", vacations.c.user_id, vacations.c.start_date, vacations.c.end_date)
Index("ix_attestations_user_dates", attestations.c.user_id, attestations.c.start_date, attestations.c.end_date)
Index("ix_users_role", users.c.role)
Index("ix_users_team_id", users.c.team_id)


def _user_properties():
        return {
                "user_id": users.c.id,
                "full_name": users.c.full_name,
                "profile": composite(
                        UserProfile,
                        users.c.registration_number,
                        users.c.cpf,
                        users.c.department,
                        users.c.position,
                        users.c.secretariat,
                        users.c.full_name,
                        users.c.start_analysis_date,
                        users.c.birth_date,
                ),
                "time_entries": relationship(DailyPonto, backref="user", order_by=daily_pontos.c.entry_date, cascade="all, delete-orphan"),
                "vacations": relationship(Vacation, backref="user", cascade="all, delete-orphan"),
                "attestations": relationship(Attestation, backref="user", order_by=attestations.c.start_date, cascade="all, delete-orphan"),
                "work_schedule": relationship(WorkSchedule, backref="user", uselist=False, cascade="all, delete-orphan"),
                "notifications": relationship(Notification, backref="user", order_by=notifications.c.created_at.desc(), cascade="all, delete-orphan"),
        }


def _column_properties(column, key):
        return {key: column}


def start_mappers():
        if hasattr(User, "__mapper__") or hasattr(CompanySettings, "__mapper__"):
                return

        mapper_registry.map_imperatively(CompanySettings, company_settings)
        mapper_registry.map_imperatively(Team, teams, properties=_column_properties(teams.c.id, "team_id"))
        mapper_registry.map_imperatively(User, users, properties=_user_properties())
        mapper_registry.map_imperatively(WorkSchedule, work_schedules, properties=_column_properties(work_schedules.c.id, "schedule_id"))
        mapper_registry.map_imperatively(DailyPonto, daily_pontos, properties=_column_properties(daily_pontos.c.id, "ponto_id"))
        mapper_registry.map_imperatively(CorrectionRequest, correction_requests, properties=_column_properties(correction_requests.c.id, "request_id"))
        mapper_registry.map_imperatively(Vacation, vacations, properties=_column_properties(vacations.c.id, "vacation_id"))
        mapper_registry.map_imperatively(Attestation, attestations, properties=_column_properties(attestations.c.id, "attestation_id"))
        mapper_registry.map_imperatively(Facultativo, facultativos, properties=_column_properties(facultativos.c.id, "facultativo_id"))
        mapper_registry.map_imperatively(Notification, notifications, properties=_column_properties(notifications.c.id, "notification_id"))
        mapper_registry.map_imperatively(AuthToken, auth_tokens, properties=_column_properties(auth_tokens.c.id, "token_id"))
        mapper_registry.map_imperatively(RateLimitEntry, rate_limit_entries, properties=_column_properties(rate_limit_entries.c.id, "entry_id"))
        mapper_registry.map_imperatively(AbsenceState, absence_state, properties=_column_properties(absence_state.c.id, "state_id"))
        mapper_registry.map_imperatively(Holiday, holidays)
        mapper_registry.map_imperatively(JourneyType, journey_types, properties=_column_properties(journey_types.c.id, "journey_id"))
        mapper_registry.map_imperatively(AuditLog, audit_logs, properties=_column_properties(audit_logs.c.id, "log_id"))

        task_properties = _column_properties(team_tasks.c.id, "task_id")
        task_properties["checklist_items"] = relationship(
                TaskChecklistItem,
                order_by=task_checklist_items.c.id,
                cascade="all, delete-orphan",
                backref="task",
        )
        mapper_registry.map_imperatively(
                TaskChecklistItem,
                task_checklist_items,
                properties=_column_properties(task_checklist_items.c.id, "checklist_item_id"),
        )
        mapper_registry.map_imperatively(TeamTask, team_tasks, properties=task_properties)
        mapper_registry.map_imperatively(
                Accomplishment,
                accomplishments,
                properties=_column_properties(accomplishments.c.id, "accomplishment_id"),
        )
        mapper_registry.map_imperatively(
                Idea,
                ideas,
                properties={
                        **_column_properties(ideas.c.id, "idea_id"),
                        "votes": relationship(IdeaVote, cascade="all, delete-orphan"),
                },
        )
        mapper_registry.map_imperatively(
                IdeaVote,
                idea_votes,
                properties=_column_properties(idea_votes.c.id, "vote_id"),
        )
        s5_properties = _column_properties(s5_audits.c.id, "s5_audit_id")
        s5_properties["items"] = relationship(
                S5Item,
                order_by=s5_items.c.id,
                cascade="all, delete-orphan",
        )
        mapper_registry.map_imperatively(
                S5Item,
                s5_items,
                properties=_column_properties(s5_items.c.id, "s5_item_id"),
        )
        mapper_registry.map_imperatively(S5Audit, s5_audits, properties=s5_properties)
        mapper_registry.map_imperatively(WikiArticle, wiki_articles, properties=_column_properties(wiki_articles.c.id, "wiki_article_id"))
        mapper_registry.map_imperatively(Mentorship, mentorships, properties=_column_properties(mentorships.c.id, "mentorship_id"))
        mapper_registry.map_imperatively(Kudos, kudos, properties=_column_properties(kudos.c.id, "kudo_id"))
        mapper_registry.map_imperatively(TeamEvent, team_events, properties=_column_properties(team_events.c.id, "event_id"))
