"""Central control center for every magic constant in the system.

Every hard-coded number, date, length, role, token lifetime, CSS-independent
window size, SMTP setting, and domain rule default lives here so the whole
application can be tuned in one place without hunting through the code.
"""
from datetime import date


# --------------------------------------------------------------------------
# Analysis window / historical dates
# --------------------------------------------------------------------------
# Default analysis start when no explicit start date is configured for a user
# or for the company. This is treated as "onboarding happened in this period".
DEFAULT_ANALYSIS_START_DATE = date(2026, 5, 1)

# Earliest fallback analysis date used when a user has no recorded start date.
FALLBACK_ANALYSIS_DATE = date(2026, 1, 1)

# strftime/strptime formats used across entrypoints for dates and times.
DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Date the daily absence checker treats as its last-run baseline before any
# real run has ever been persisted (used in non-production contexts).
ABSENCE_DEFAULT_LAST_CHECK_DATE = date(2026, 5, 10)

# Years for which fixed Brazilian holidays are seeded.
HOLIDAY_SEED_YEAR_START = 2025
HOLIDAY_SEED_YEAR_END = 2036  # exclusive upper bound

# --------------------------------------------------------------------------
# Time / clock rules
# --------------------------------------------------------------------------
# Brasília timezone is UTC-3; we shift the UTC wall clock by this many hours.
BRAZIL_UTC_OFFSET_HOURS = 3

# Work carried on a 12x36 rotation falls on even/odd days relative to the
# rotation start date; modulo divisor for that cycle length (2 days).
ROTATION_CYCLE_DAYS = 2

# A standard work week runs Monday (0) through Friday (4).
LAST_WORKDAY_WEEKDAY = 5  # exclusive upper bound for weekday()

# Default tolerance in minutes before "late" is flagged.
DEFAULT_TOLERANCE_MINUTES = 15

# Serialized schedule regime values used in forms and services.
SCHEDULE_STANDARD = "standard"
SCHEDULE_12X36 = "12x36"

# Recurring structural denominators.
MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24
MILLISECONDS_PER_SECOND = 1000
SECONDS_PER_MINUTE = 60

# --------------------------------------------------------------------------
# Weekly absence-check window
# --------------------------------------------------------------------------
# Monday is weekday() == 0; when the checker runs on Monday it also verifies
# the weekend (Sat/Sun) plus Friday, i.e. the last 3 days.
MONDAY_WEEKDAY_INDEX = 0
MONDAY_BACKLOG_DAYS = 3  # on Monday: check today-back this far
PREVIOUS_DAY_OFFSET = 1  # on other weekdays: check yesterday only

# --------------------------------------------------------------------------
# Roles
# --------------------------------------------------------------------------
# Users holding any of these can access the management panel.
MANAGEMENT_ROLES = ["manager", "admin", "gestor"]
# Users holding any of these can access admin-only features (audit, settings).
ADMIN_ROLES = ["admin", "gestor"]
# Roles considered "manager level" for permission checks and self-review guard.
MANAGER_LEVEL_ROLES = ["manager", "admin", "gestor"]
# The serialized role value used by the decorators as the base manager level.
MANAGER_ROLE_VALUE = "manager"
ADMIN_ROLE_VALUE = "admin"

# Serialized role values.
ROLE_EMPLOYEE = "employee"
ROLE_MANAGER = "manager"
ROLE_GESTOR = "gestor"
ROLE_ADMIN = "admin"

# Role display labels used by the template helper.
ROLE_LABELS = {
        ROLE_EMPLOYEE: "Funcionário",
        ROLE_MANAGER: "Diretor",
        ROLE_ADMIN: "Secretário",
}

# --------------------------------------------------------------------------
# Attendance / absence mark-up strings
# --------------------------------------------------------------------------
MANAGER_NOTES_VACATION = "Férias"
MISSING_LOCATION_AUTOMATIC = "Sistema: Falta automática (Verificação diária)."
MISSING_NOTES_AUTOMATIC = "Ausência sem registro de ponto."
EMPTY_ENTRY_MISSING_REASON = "por ausência de registro."
BLANK_SCHEDULE_MISSING_REASON = "(Usuário sem escala definida)."
RETROACTIVE_LOCATION_MISSING = "Sistema: Lançamento retroativo (sem horários)."
RETROACTIVE_NOTE_SCHEDULE = "Lançamento retroativo (horários da jornada)."
RETROACTIVE_NOTE_MANUAL = "Lançamento retroativo (horários manuais)."
RETROACTIVE_NOTES_AUTO = "Ausência sem registro de ponto (lançamento retroativo)."
RETROACTIVE_NOTE_FILLED = "Preenchido retroativamente."

# --------------------------------------------------------------------------
# Authentication token lifetimes (seconds)
# --------------------------------------------------------------------------
PASSWORD_RESET_TOKEN_MAX_AGE = 3600  # 1 hour
MAGIC_LOGIN_TOKEN_MAX_AGE = 600  # 10 minutes
INVITE_TOKEN_MAX_AGE = 604800  # 7 days
TOKEN_SALT_PASSWORD_RESET = "password-reset-salt"
TOKEN_SALT_MAGIC_LOGIN = "magic-login-salt"
TOKEN_SALT_INVITE = "invite-salt"

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
LOCAL_SQLITE_URL = "sqlite:///banco_de_horas.db"
VERCEL_SQLITE_URL = "sqlite:////tmp/banco_de_horas.db"
POSTGRES_SCHEME_POSTGRES = "postgres://"
POSTGRES_SCHEME_POSTGRESQL = "postgresql://"

# Column length / schema limits (also reflected in DB columns; change with care).
ROLE_COLUMN_LENGTH = 50
EMAIL_COLUMN_LENGTH = 255
PASSWORD_COLUMN_LENGTH = 255
AUDIT_ACTION_COLUMN_LENGTH = 255
NAME_COLUMN_LENGTH = 100
REGISTRATION_NUMBER_COLUMN_LENGTH = 50
CPF_COLUMN_LENGTH = 14
DEPARTMENT_COLUMN_LENGTH = 100
POSITION_COLUMN_LENGTH = 100
SECRETARIAT_COLUMN_LENGTH = 100
FULL_NAME_COLUMN_LENGTH = 255
LOCATION_DATA_COLUMN_LENGTH = 1000
NOTES_COLUMN_LENGTH = 1000
MANAGER_NOTES_COLUMN_LENGTH = 1000
CORRECTION_STAGE_COLUMN_LENGTH = 50
CORRECTION_STATUS_COLUMN_LENGTH = 20
ATTESTATION_CID_COLUMN_LENGTH = 20
FACULTATIVO_DESCRIPTION_COLUMN_LENGTH = 255
HOLIDAY_DESCRIPTION_COLUMN_LENGTH = 255
NOTIFICATION_MESSAGE_COLUMN_LENGTH = 500
TOKEN_KIND_COLUMN_LENGTH = 20
TOKEN_HASH_COLUMN_LENGTH = 64
TOKEN_KIND_RESET = "reset"
TOKEN_KIND_INVITE = "invite"

# --------------------------------------------------------------------------
# SMTP / email
# --------------------------------------------------------------------------
DEFAULT_SMTP_SERVER = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 587
SMTP_SSL_PORT = 465
SMTP_TIMEOUT_SECONDS = 8
EMAIL_FROM_NAME = "Banco de Horas"
EMAIL_SUBJECT_NOTIFICATION = "Nova Notificação - Banco de Horas"

# --------------------------------------------------------------------------
# Dashboard / list display caps
# --------------------------------------------------------------------------
MAX_NOTIFICATIONS_DISPLAYED = 20
MAX_AUDIT_LOGS_DISPLAYED = 200
RECENT_ENTRIES_DEFAULT_COUNT = 10

# --------------------------------------------------------------------------
# Duplicate clock-in guard (mirrors the 15-minute rule used by the UI)
# --------------------------------------------------------------------------
DUPLICATE_CLOCK_MINUTES = 15

# --------------------------------------------------------------------------
# Geolocation
# --------------------------------------------------------------------------
GEOLOCATION_TIMEOUT_MS = 10000
GEOLOCATION_HIGH_ACCURACY = True
MAPS_EMBED_URL = "https://www.google.com/maps?q={loc}&output=embed"

# --------------------------------------------------------------------------
# Input masks
# --------------------------------------------------------------------------
CPF_MAX_LENGTH = 11
CPF_MASK_GROUPS = [3, 3, 3, 2]
TIME_MASK_MAX_LENGTH = 6
REGISTRATION_MAX_LENGTH = 10

# --------------------------------------------------------------------------
# Excel report geometry
# --------------------------------------------------------------------------
REPORT_SHEET_NAME = "Relatório de Ponto"
REPORT_COLUMN_WIDTHS = [12, 12, 12, 12, 12, 12, 15, 30]
REPORT_TITLE_CELL = "A1"
REPORT_TITLE_END_COLUMN = "H"
REPORT_PERIOD_CELL = "A2"
REPORT_PERIOD_END_COLUMN = "H"
REPORT_TITLE_TEXT = "RELATÓRIO MENSAL DE FREQUÊNCIA"
REPORT_HEADER_ROW = 8  # the styled column header row (1-indexed)
REPORT_FIRST_DATA_ROW = 9
REPORT_LAST_COLUMN = 8
REPORT_SIGNATURE_GAP_ROWS = 3
REPORT_FONT_NAME = "Arial"
REPORT_TITLE_FONT_SIZE = 14
REPORT_HEADER_FONT_SIZE = 10
REPORT_LABEL_FONT_SIZE = 9
REPORT_VALUE_FONT_SIZE = 9
REPORT_HEADER_FILL_COLOR = "F2F2F2"
REPORT_SIGNATURE_EMPLOYEE_COLUMNS = ("A", "C")
REPORT_SIGNATURE_MANAGER_COLUMNS = ("F", "H")

# --------------------------------------------------------------------------
# Fixed Brazilian national + regional holidays (month, day, description)
# --------------------------------------------------------------------------
FIXED_NATIONAL_HOLIDAYS = [
        (1, 1, "Confraternização Universal (Ano Novo)"),
        (4, 21, "Tiradentes"),
        (5, 1, "Dia do Trabalhador"),
        (9, 7, "Independência do Brasil"),
        (10, 12, "Nossa Senhora Aparecida (Padroeira do Brasil)"),
        (11, 2, "Finados"),
        (11, 15, "Proclamação da República"),
        (11, 20, "Dia Nacional de Zumbi e da Consciência Negra"),
        (12, 25, "Natal"),
]

FIXED_VALADARES_HOLIDAYS = [
        (1, 30, "Aniversário de Governador Valadares"),
        (6, 13, "Santo Antônio (Padroeiro de Governador Valadares)"),
]

# Day offsets relative to Easter Sunday for movable holidays.
EASTER_OFFSET_CARNAVAL = -47
EASTER_OFFSET_GOOD_FRIDAY = -2
EASTER_OFFSET_CORPUS_CHRISTI = 60

# --------------------------------------------------------------------------
# Anomaly stage attribute names (mirrors the model's column naming)
# --------------------------------------------------------------------------
# (flag, reviewed, approved, excused) attribute tuples shared by the domain and
# by the administration/clock services so they stay in sync in one place.
ANOMALY_STAGE_FLAGS = [
        ("arrival_late", "arrival_late_reviewed", "arrival_late_approved", "arrival_late_excused"),
        ("lunch_start_late", "lunch_start_late_reviewed", "lunch_start_late_approved", "lunch_start_late_excused"),
        ("lunch_start_early", "lunch_start_early_reviewed", "lunch_start_early_approved", "lunch_start_early_excused"),
        ("lunch_end_late", "lunch_end_late_reviewed", "lunch_end_late_approved", "lunch_end_late_excused"),
        ("departure_early", "departure_early_reviewed", "departure_early_approved", "departure_early_excused"),
]

# Anomaly decision attribute triples (reviewed, approved, excused) keyed per stage.
ANOMALY_DECISION_FLAGS = {
        "arrival": ("arrival_late_reviewed", "arrival_late_approved", "arrival_late_excused"),
        "lunch_start": ("lunch_start_late_reviewed", "lunch_start_late_approved", "lunch_start_late_excused"),
        "lunch_start_early": ("lunch_start_early_reviewed", "lunch_start_early_approved", "lunch_start_early_excused"),
        "lunch_end": ("lunch_end_late_reviewed", "lunch_end_late_approved", "lunch_end_late_excused"),
        "departure": ("departure_early_reviewed", "departure_early_approved", "departure_early_excused"),
        "missing": ("missing_reviewed", "missing_approved", "missing_excused"),
}

# Reviewed/approved/excused attribute triples (without the leading flag), used
# when excuses are reset or applied globally.
ANOMALY_FLAG_TRIPLES = [
        ("arrival_late_reviewed", "arrival_late_approved", "arrival_late_excused"),
        ("lunch_start_late_reviewed", "lunch_start_late_approved", "lunch_start_late_excused"),
        ("lunch_start_early_reviewed", "lunch_start_early_approved", "lunch_start_early_excused"),
        ("lunch_end_late_reviewed", "lunch_end_late_approved", "lunch_end_late_excused"),
        ("departure_early_reviewed", "departure_early_approved", "departure_early_excused"),
]

# --------------------------------------------------------------------------
# Clock-in / clock-out stages
# --------------------------------------------------------------------------
STAGE_ARRIVAL = "arrival"
STAGE_LUNCH_START = "lunch_start"
STAGE_LUNCH_START_EARLY = "lunch_start_early"
STAGE_LUNCH_END = "lunch_end"
STAGE_DEPARTURE = "departure"
STAGE_MISSING = "missing"
NEXT_STAGE_ORDER = [STAGE_ARRIVAL, STAGE_LUNCH_START, STAGE_LUNCH_END, STAGE_DEPARTURE]

# Stage display labels / messages.
STAGE_LABELS = {
        STAGE_ARRIVAL: "Chegada",
        STAGE_LUNCH_START: "Saída Almoço",
        STAGE_LUNCH_END: "Retorno Almoço",
        STAGE_DEPARTURE: "Fim Jornada",
}
STAGE_READY_MESSAGES = {
        STAGE_ARRIVAL: "Chegada registrada",
        STAGE_LUNCH_START: "Saída para almoço registrada",
        STAGE_LUNCH_END: "Retorno do almoço registrado",
        STAGE_DEPARTURE: "Fim de jornada registrado",
}

# Location label texts written into the day's log.
CLOCK_LOCATION_NA = "Não obtida"
LOCATION_PREFIX_ARRIVAL = "Chegada"
LOCATION_PREFIX_LUNCH_START = "Almoço (Sai)"
LOCATION_PREFIX_LUNCH_END = "Almoço (Vol)"
LOCATION_PREFIX_DEPARTURE = "Fim"
LOCATION_SEPARATOR = " | "

# Correction-request statuses.
CORRECTION_STATUS_PENDING = "pending"
CORRECTION_STATUS_APPROVED = "approved"
CORRECTION_STATUS_REJECTED = "rejected"

# Anomaly decision actions.
ANOMALY_ACTION_APPROVE = "approve"
ANOMALY_ACTION_EXCUSE = "excuse"
