from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
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

class WorkScheduleForm(FlaskForm):
    journey_type = SelectField("Journey Type Template", choices=[], coerce=int)
    arrival = StringField("Expected Arrival (HH:MM)", validators=[DataRequired()])
    lunch_start = StringField("Lunch Start (HH:MM)", validators=[DataRequired()])
    lunch_end = StringField("Lunch End (HH:MM)", validators=[DataRequired()])
    departure = StringField("Expected Departure (HH:MM)", validators=[DataRequired()])
    tolerance = StringField("Tolerance (minutes)", default="15", validators=[DataRequired()])
    save_as_new = StringField("Save as New Journey Type (Name)", validators=[])
    submit = SubmitField("Save Schedule")

class JourneyTypeForm(FlaskForm):
    name = StringField("Journey Name", validators=[DataRequired()])
    arrival = StringField("Expected Arrival (HH:MM)", validators=[DataRequired()])
    lunch_start = StringField("Lunch Start (HH:MM)", validators=[DataRequired()])
    lunch_end = StringField("Lunch End (HH:MM)", validators=[DataRequired()])
    departure = StringField("Expected Departure (HH:MM)", validators=[DataRequired()])
    tolerance = StringField("Tolerance (minutes)", default="15", validators=[DataRequired()])
    submit = SubmitField("Create Journey Type")
