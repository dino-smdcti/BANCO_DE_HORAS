from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Acesso restrito a administradores.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function

def manager_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ["manager", "admin"]:
            flash("Acesso restrito a gestores.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function

def handle_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("dashboard"))
        except PermissionError as e:
            flash(str(e), "danger")
            return redirect(url_for("dashboard"))
        except Exception as e:
            # Displaying the actual error for debugging during the fix process
            flash(f"Erro: {str(e)}", "danger")
            return redirect(url_for("dashboard"))
    return decorated_function
