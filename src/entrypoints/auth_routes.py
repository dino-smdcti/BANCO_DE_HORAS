import os

from flask import flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from src.entrypoints import flask_app
from src.entrypoints.forms import LoginForm
from src.entrypoints.web_helpers import new_uow


def register_routes(app):
        app.add_url_rule("/", "index", index)
        app.add_url_rule("/favicon.ico", "favicon", favicon)
        app.add_url_rule("/login", "login", login, methods=["GET", "POST"])
        app.add_url_rule("/logout", "logout", logout)
        app.add_url_rule("/forgot-password", "forgot_password", forgot_password, methods=["GET", "POST"])
        app.add_url_rule("/reset-password/<token>", "reset_password", reset_password, methods=["GET", "POST"])
        app.add_url_rule("/magic-login", "magic_login", magic_login, methods=["POST"])
        app.add_url_rule("/login-link/<token>", "magic_link_login", magic_link_login)


def index():
        return render_template("index.html")


def favicon():
        static_dir = os.path.join(flask_app.app.root_path, "static")
        return send_from_directory(static_dir, "favicon.ico", mimetype="image/vnd.microsoft.icon")


def login():
        form = LoginForm()
        if form.validate_on_submit():
                return _login_post(form)
        return render_template("login.html", form=form)


def logout():
        logout_user()
        return redirect(url_for("index"))


def forgot_password():
        if request.method == "POST":
                return _handle_forgot_post(request.form.get("email"))
        return render_template("forgot_password.html")


def reset_password(token):
        email = _load_email_from_token(token)
        if not email:
                flash("O link de recuperação é inválido ou expirou.", "danger")
                return redirect(url_for("forgot_password"))
        if request.method == "POST":
                password = request.form.get("password")
                if not password:
                        flash("A senha é obrigatória.", "danger")
                        return render_template("reset_password.html", token=token)
                _apply_new_password(email, password)
                return redirect(url_for("login"))
        return render_template("reset_password.html", token=token)


def magic_login():
        email = request.form.get("email")
        if not email:
                flash("E-mail é obrigatório.", "warning")
                return redirect(url_for("login"))
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
                if user and check_password_hash(user.password_hash, form.password.data):
                        login_user(flask_app.AuthenticatedUser(user))
                        return _post_login_redirect(user)
        flash("E-mail ou senha inválidos", "danger")
        return render_template("login.html", form=form)


def _post_login_redirect(user):
        if not user.is_profile_complete:
                return redirect(url_for("complete_profile"))
        if user.role == "employee" and not user.work_schedule:
                return redirect(url_for("choose_journey"))
        return redirect(url_for("dashboard"))


def _load_email_from_token(token):
        try:
                return flask_app.serializer.loads(token, salt="password-reset-salt", max_age=3600)
        except Exception:
                return None


def _load_magic_email(token):
        try:
                return flask_app.serializer.loads(token, salt="magic-login-salt", max_age=600)
        except Exception:
                return None


def _handle_forgot_post(email):
        uow = new_uow()
        with uow:
                user = uow.users.get_user_by_email(email)
                if user:
                        token = flask_app.serializer.dumps(email, salt="password-reset-salt")
                        reset_url = url_for("reset_password", token=token, _external=True)
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


def _apply_new_password(email, password):
        uow = new_uow()
        with uow:
                user = uow.users.get_user_by_email(email)
                if user:
                        user.password_hash = generate_password_hash(password)
                        uow.commit()
                        flash("Sua senha foi atualizada com sucesso.", "success")


def _handle_magic_login(email):
        uow = new_uow()
        with uow:
                user = uow.users.get_user_by_email(email)
                if user:
                        token = flask_app.serializer.dumps(email, salt="magic-login-salt")
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
