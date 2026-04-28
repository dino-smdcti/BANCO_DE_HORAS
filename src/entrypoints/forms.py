from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password")])
    role = SelectField("Role", choices=[("employee", "Employee"), ("manager", "Manager")], validators=[DataRequired()])
    submit = SubmitField("Register")

class ProfileForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired()])
    registration_number = StringField("Matrícula", validators=[DataRequired()])
    cpf = StringField("CPF", validators=[DataRequired(), Length(min=11, max=14)])
    department = StringField("Department", validators=[DataRequired()])
    position = StringField("Position", validators=[DataRequired()])
    secretariat = StringField("Secretariat", validators=[DataRequired()])
    submit = SubmitField("Complete Profile")
