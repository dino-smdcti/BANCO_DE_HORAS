from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo

class LoginForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(), Email()])
    password = PasswordField("Senha", validators=[DataRequired()])
    submit = SubmitField("Entrar")

class RegisterForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(), Email()])
    role = SelectField("Perfil", choices=[("employee", "Funcionário"), ("manager", "Gestor")], validators=[DataRequired()])
    submit = SubmitField("Cadastrar")

class ProfileForm(FlaskForm):
    full_name = StringField("Nome Completo", validators=[DataRequired()])
    registration_number = StringField("Matrícula", validators=[DataRequired()])
    cpf = StringField("CPF", validators=[DataRequired(), Length(min=11, max=14)])
    department = StringField("Departamento", validators=[DataRequired()])
    position = StringField("Cargo", validators=[DataRequired()])
    secretariat = StringField("Secretaria", validators=[DataRequired()])
    submit = SubmitField("Completar Perfil")

class WorkScheduleForm(FlaskForm):
    journey_type = SelectField("Template de Jornada", choices=[], coerce=int)
    arrival = StringField("Chegada Esperada (HH:MM)", validators=[DataRequired()])
    lunch_start = StringField("Início Almoço (HH:MM)", validators=[DataRequired()])
    lunch_end = StringField("Fim Almoço (HH:MM)", validators=[DataRequired()])
    departure = StringField("Saída Esperada (HH:MM)", validators=[DataRequired()])
    tolerance = StringField("Tolerância (minutos)", default="15", validators=[DataRequired()])
    save_as_new = StringField("Salvar como Novo Tipo (Nome)", validators=[])
    submit = SubmitField("Salvar Horário")

class JourneyTypeForm(FlaskForm):
    name = StringField("Nome da Jornada", validators=[DataRequired()])
    arrival = StringField("Chegada Esperada (HH:MM)", validators=[DataRequired()])
    lunch_start = StringField("Início Almoço (HH:MM)", validators=[DataRequired()])
    lunch_end = StringField("Fim Almoço (HH:MM)", validators=[DataRequired()])
    departure = StringField("Saída Esperada (HH:MM)", validators=[DataRequired()])
    tolerance = StringField("Tolerância (minutos)", default="15", validators=[DataRequired()])
    submit = SubmitField("Criar Tipo de Jornada")
