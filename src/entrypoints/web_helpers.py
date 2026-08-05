from datetime import datetime

MANAGEMENT_ROLES = ["manager", "admin", "gestor"]
INVALID_DATE = object()


def new_uow():
        """Build a fresh unit of work, resolved through the app module so tests can patch it."""
        from src.entrypoints import flask_app
        return flask_app.SqlAlchemyUnitOfWork()


def is_management_role(role_value):
        return role_value in MANAGEMENT_ROLES


def get_maps_url(location_str):
        if not location_str or "," not in location_str:
                return None
        return f"https://www.google.com/maps?q={location_str.strip()}&output=embed"


def parse_time(value):
        """Parse a time string, returning None when empty or unparseable."""
        if not value:
                return None
        for fmt in ("%H:%M:%S", "%H:%M"):
                parsed = _try_parse_time(value, fmt)
                if parsed is not None:
                        return parsed
        return None


def _try_parse_time(value, fmt):
        try:
                return datetime.strptime(value, fmt).time()
        except ValueError:
                return None


def parse_date(value):
        """Parse an ISO date string; None when empty, INVALID_DATE when malformed."""
        if not value:
                return None
        try:
                return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
                return INVALID_DATE
