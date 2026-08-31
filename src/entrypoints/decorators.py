import sys
import traceback
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user
from src.config import ADMIN_ROLES, ADMIN_ROLE_VALUE, MANAGER_LEVEL_ROLES, MANAGER_ROLE_VALUE

def admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
                return _guard_role(f, ADMIN_ROLE_VALUE, *args, **kwargs)
        return decorated_function


def manager_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
                return _guard_role(f, MANAGER_ROLE_VALUE, *args, **kwargs)
        return decorated_function


def handle_errors(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
                return _run_guarded(f, *args, **kwargs)
        return decorated_function


def _guard_role(f, level, *args, **kwargs):
        roles = _roles_for(level)
        if not current_user.is_authenticated or current_user.role not in roles:
                flash(_denial_message(level), "danger")
                return redirect(url_for("dashboard"))
        return f(*args, **kwargs)


def _run_guarded(f, *args, **kwargs):
        try:
                return f(*args, **kwargs)
        except Exception as e:
                traceback.print_exc(file=sys.stderr)
                flash(f"Erro detalhado: {str(e)}", "danger")
                return redirect(url_for("dashboard"))


def _roles_for(level):
        if level == ADMIN_ROLE_VALUE:
                return ADMIN_ROLES
        return MANAGER_LEVEL_ROLES


def _denial_message(level):
        if level == ADMIN_ROLE_VALUE:
                return "Acesso restrito a administradores."
        return "Acesso restrito a gestores."
