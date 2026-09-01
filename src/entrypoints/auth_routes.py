import os

from flask import flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from src.entrypoints import flask_app
from src.entrypoints.forms import LoginForm
from src.entrypoints.web_helpers import new_uow
from src.config import (
        MAGIC_LOGIN_TOKEN_MAX_AGE,
        PASSWORD_RESET_TOKEN_MAX_AGE,
        ROLE_EMPLOYEE,
        RATE_LIMIT_STATUS_CODE,
        TOKEN_KIND_INVITE,
        TOKEN_KIND_RESET,
        TOKEN_SALT_MAGIC_LOGIN,
)
from src.service_layer import token_service
from src.service_layer import rate_limit_service


def register_routes(app):
        app.add_url_rule("/", "index", index)
        app.add_url_rule("/favicon.ico", "favicon", favicon)
        app.add_url_rule("/login", "login", login, methods=["GET", "POST"])
        app.add_url_rule("/logout", "logout", logout)
        app.add_url_rule("/forgot-password", "forgot_password", forgot_password, methods=["GET", "POST"])
        app.add_url_rule("/reset-password/<token>", "reset_password", reset_password, methods=["GET", "POST"])
        app.add_url_rule("/invite/<token>", "accept_invite", accept_invite, methods=["GET", "POST"])
        app.add_url_rule("/magic-login", "magic_login", magic_login, methods=["POST"])
        app.add_url_rule("/login-link/<token>", "magic_link_login", magic_link_login)


def index():
        return render_template("index.html")


def favicon():
        static_dir = os.path.join(flask_app.app.root_path, "static")
        return send_from_directory(static_dir, "favicon.ico", mimetype="image/vnd.microsoft.icon")


def _client_ip():
        """Return the best-effort client IP for rate-limit bucketing."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
                return forwarded.split(",")[0].strip()
        return request.remote_addr or "unknown"


def _throttled(kind, scope=""):
        """Rate-limit an auth attempt; returns a 429 status when throttled, else None."""
        scope = scope or _client_ip()
        if rate_limit_service.is_allowed(new_uow(), kind, scope):
                return None
        return RATE_LIMIT_STATUS_CODE


def _abort_throttled():
        return f"Too many attempts. Please try again later.", RATE_LIMIT_STATUS_CODE


def login():
        form = LoginForm()
        if form.validate_on_submit():
                if _throttled("auth"):
                        return _abort_throttled()
                return _login_post(form)
        return render_template("login.html", form=form)


def logout():
        logout_user()
        return redirect(url_for("index"))


def forgot_password():
        if request.method == "POST":
                if _throttled("auth"):
                        return _abort_throttled()
                return _handle_forgot_post(request.form.get("email"))
        return render_template("forgot_password.html")


def reset_password(token):
        uow = new_uow()
        with uow:
                user = _validated_reset_user(uow, token, TOKEN_KIND_RESET)
                if user is None:
                        flash("O link de recuperação é inválido ou expirou.", "danger")
                        return redirect(url_for("forgot_password"))
                if request.method == "POST":
                        password = request.form.get("password")
                        if not password:
                                flash("A senha é obrigatória.", "danger")
                                return render_template("reset_password.html", token=token)
                        _apply_new_password(uow, user, token, TOKEN_KIND_RESET, password)
                        return redirect(url_for("login"))
                return render_template("reset_password.html", token=token)


def accept_invite(token):
        """Set up a new password for an invited user. Uses a distinct token kind
        from password reset so an invite link cannot double as a reset (and vice versa)."""
        uow = new_uow()
        with uow:
                user = _validated_reset_user(uow, token, TOKEN_KIND_INVITE)
                if user is None:
                        flash("O convite é inválido ou expirou.", "danger")
                        return redirect(url_for("forgot_password"))
                if request.method == "POST":
                        password = request.form.get("password")
                        if not password:
                                flash("A senha é obrigatória.", "danger")
                                return render_template("reset_password.html", token=token)
                        _apply_new_password(uow, user, token, TOKEN_KIND_INVITE, password)
                        return redirect(url_for("login"))
                return render_template("reset_password.html", token=token)


def magic_login():
        email = request.form.get("email")
        if not email:
                flash("E-mail é obrigatório.", "warning")
                return redirect(url_for("login"))
        if _throttled("auth"):
                return _abort_throttled()
        return _handle_magic_login(email)


def magic_link_login(token):
        email = _load_magic_email(token)
        if not email:
                flash("O link de acesso é inválido ou expirou.", "danger")
                return redirect(url_for("login"))
        uow = new_uow()
        with uow:
                user = uow.users.get_user_by_email(email)
                if user:
                        login_user(flask_app.AuthenticatedUser(user))
                        return _post_login_redirect(user)
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("login"))


def _login_post(form):
        uow = new_uow()
        with uow:
                user = uow.users.get_user_by_email(form.email.data)
                if user and user.password_set and check_password_hash(user.password_hash, form.password.data):
                        login_user(flask_app.AuthenticatedUser(user))
                        return _post_login_redirect(user)
        flash("E-mail ou senha inválidos", "danger")
        return render_template("login.html", form=form)


def _post_login_redirect(user):
        if not user.is_profile_complete:
                return redirect(url_for("complete_profile"))
        if user.role == ROLE_EMPLOYEE and not user.work_schedule:
                return redirect(url_for("choose_journey"))
        return redirect(url_for("dashboard"))


def _load_magic_email(token):
        try:
                return flask_app.serializer.loads(token, salt=TOKEN_SALT_MAGIC_LOGIN, max_age=MAGIC_LOGIN_TOKEN_MAX_AGE)
        except Exception:
                return None


def _validated_reset_user(uow, token, kind):
        user_id = token_service.peek_token(uow, token, kind)
        if user_id is None:
                return None
        return uow.users.get_user_by_id(user_id)


def _handle_forgot_post(email):
        uow = new_uow()
        with uow:
                user = uow.users.get_user_by_email(email)
                if user:
                        raw = token_service.issue_token(uow, user.user_id, TOKEN_KIND_RESET, PASSWORD_RESET_TOKEN_MAX_AGE)
                        reset_url = url_for("reset_password", token=raw, _external=True)
                        html = render_template("emails/reset_password.html", reset_url=reset_url)
                        _send_reset_email(email, html)
                else:
                        _flash_generic_reset_info()
        return redirect(url_for("login"))


def _send_reset_email(email, html):
        if flask_app.send_email(email, "Recuperação de Senha - Banco de Horas", html):
                _flash_generic_reset_info()
        else:
                flash("Erro ao enviar o e-mail de recuperação. Por favor, tente novamente mais tarde.", "danger")


def _flash_generic_reset_info():
        flash("Se o e-mail estiver cadastrado, você receberá um link de recuperação em instantes.", "info")


def _apply_new_password(uow, user, token, kind, password):
        token_service.consume_token(uow, token, kind)
        user.password_hash = generate_password_hash(password)
        user.password_set = True
        uow.tokens.revoke_user_tokens(user.user_id, TOKEN_KIND_RESET)
        uow.commit()
        flash("Sua senha foi atualizada com sucesso.", "success")


def _handle_magic_login(email):
        uow = new_uow()
        with uow:
                user = uow.users.get_user_by_email(email)
                if user:
                        token = flask_app.serializer.dumps(email, salt=TOKEN_SALT_MAGIC_LOGIN)
                        login_url = url_for("magic_link_login", token=token, _external=True)
                        html = render_template("emails/magic_link.html", login_url=login_url)
                        _send_magic_email(email, html)
                else:
                        _flash_generic_reset_info()
        return redirect(url_for("login"))


def _send_magic_email(email, html):
        if flask_app.send_email(email, "Link de Acesso Rápido - Banco de Horas", html):
                _flash_generic_reset_info()
        else:
                flash("Erro ao enviar o e-mail de acesso. Por favor, tente novamente mais tarde.", "danger")
