from datetime import datetime

from flask import flash, redirect, url_for

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


def parse_date_arg(value):
        """Parse a date string that must be present and valid.

        Matches ``datetime.strptime(value, DATE_FORMAT).date()`` semantics:
        raises ValueError when the value is empty or malformed. Callers that
        expect the value to be well-formed should use this instead of the
        lenient ``parse_date``.
        """
        return datetime.strptime(value, DATE_FORMAT).date()


def parse_time_arg(value):
        """Parse a time string that must be present and valid (raises ValueError otherwise)."""
        return datetime.strptime(value, TIME_FORMAT).time()


def redirect_to_employee_logs(employee_id):
        """Redirect to the employee logs page for the given employee."""
        return redirect(url_for("view_employee_logs", employee_id=employee_id))


def flash_redirect(endpoint, message, category="danger", **values):
        """Flash ``message`` and redirect to ``endpoint`` (standard error/notice idiom)."""
        flash(message, category)
        return redirect(url_for(endpoint, **values))
