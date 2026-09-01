"""Standard route decorators.

Ordering convention (top to bottom, outermost first):

    @login_required
    @<role guard>          # admin_required / manager_required / role_required
    @handle_errors         # innermost, wraps the actual handler

The role guard must sit above (outermost of) ``@handle_errors`` so that
permission denials short-circuit with a redirect before error handling wraps
the handler, and ``@login_required`` must sit outermost so authentication is
checked before authorization.
"""
import sys
import traceback
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user
from src.config import ADMIN_ROLES, MANAGER_LEVEL_ROLES


def role_required(*roles, deny_message="Acesso restrito."):
        """Standard role guard factory.

        Denies any request whose ``current_user`` is unauthenticated or whose
        ``role`` is not one of ``roles``, flashing ``deny_message`` and
        redirecting to the dashboard.
        """
        allowed = frozenset(roles)

        def decorator(f):
                @wraps(f)
                def decorated_function(*args, **kwargs):
                        return _guard_role(f, allowed, deny_message, *args, **kwargs)
                return decorated_function

        return decorator


def admin_required(f):
        """Allow only administration-level roles (see ``ADMIN_ROLES``)."""
        return role_required(*ADMIN_ROLES, deny_message="Acesso restrito a administradores.")(f)


def manager_required(f):
        """Allow only management-level roles (see ``MANAGER_LEVEL_ROLES``)."""
        return role_required(*MANAGER_LEVEL_ROLES, deny_message="Acesso restrito a gestores.")(f)


def handle_errors(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
                return _run_guarded(f, *args, **kwargs)
        return decorated_function


def _guard_role(f, roles, deny_message, *args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in roles:
                flash(deny_message, "danger")
                return redirect(url_for("dashboard"))
        return f(*args, **kwargs)


def _run_guarded(f, *args, **kwargs):
        try:
                return f(*args, **kwargs)
        except Exception as e:
                traceback.print_exc(file=sys.stderr)
                flash(f"Erro detalhado: {str(e)}", "danger")
                return redirect(url_for("dashboard"))