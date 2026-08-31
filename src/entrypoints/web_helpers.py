from datetime import datetime

from src.config import DATE_FORMAT, MANAGEMENT_ROLES, MAPS_EMBED_URL, TIME_FORMAT

MANAGEMENT_ROLES = MANAGEMENT_ROLES
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
        return MAPS_EMBED_URL.format(loc=location_str.strip())


def parse_time(value):
        """Parse a time string, returning None when empty or unparseable."""
        if not value:
                return None
        for fmt in (f"{TIME_FORMAT}:%S", TIME_FORMAT):
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
                return datetime.strptime(value, DATE_FORMAT).date()
        except ValueError:
                return INVALID_DATE
