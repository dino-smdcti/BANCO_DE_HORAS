from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, BooleanField, DateField
from wtforms.validators import DataRequired, Email, Optional
from src.config import DEFAULT_TOLERANCE_MINUTES, ROLE_EMPLOYEE, ROLE_MANAGER, SCHEDULE_12X36, SCHEDULE_STANDARD

class LoginForm(FlaskForm):
        email = StringField("E-mail", validators=[DataRequired(), Email()])
        password = PasswordField("Senha", validators=[DataRequired()])
        submit = SubmitField("Entrar")


class RegisterForm(FlaskForm):
        email = StringField("E-mail", validators=[DataRequired(), Email()])
        role = SelectField("Perfil", choices=[(ROLE_EMPLOYEE, "Funcionário"), (ROLE_MANAGER, "Gestor")], validators=[DataRequired()])
        submit = SubmitField("Cadastrar")


class ProfileForm(FlaskForm):
        full_name = StringField("Nome Completo", validators=[DataRequired()])
        registration_number = StringField("Matrícula")
        cpf = StringField("CPF")
        department = StringField("Departamento", validators=[DataRequired()])
        position = StringField("Cargo", validators=[DataRequired()])
        secretariat = StringField("Secretaria", validators=[DataRequired()])
        birth_date = DateField("Data de Nascimento", format="%Y-%m-%d", validators=[Optional()])
        submit = SubmitField("Completar Perfil")


class WorkScheduleForm(FlaskForm):
        journey_type = SelectField("Template de Jornada", choices=[], coerce=int)
        schedule_type = SelectField("Regime de Trabalho", choices=[(SCHEDULE_STANDARD, "Padrão (Seg-Sex)"), (SCHEDULE_12X36, "Plantão 12x36")], default=SCHEDULE_STANDARD)
        rotation_start_date = StringField("Início do Ciclo (12x36 - AAAA-MM-DD)")
        has_lunch_break = BooleanField("Possui intervalo de almoço?")
        arrival = StringField("Chegada Esperada (HH:MM)", validators=[DataRequired()])
        lunch_start = StringField("Início Almoço (HH:MM)")
        lunch_end = StringField("Fim Almoço (HH:MM)")
        departure = StringField("Saída Esperada (HH:MM)", validators=[DataRequired()])
        tolerance = StringField("Tolerância (minutos)", default=str(DEFAULT_TOLERANCE_MINUTES), validators=[DataRequired()])
        save_as_new = StringField("Salvar como Novo Tipo (Nome)", validators=[])
        submit = SubmitField("Salvar Horário")


class JourneyTypeForm(FlaskForm):
        name = StringField("Nome da Jornada", validators=[DataRequired()])
        schedule_type = SelectField("Regime de Trabalho", choices=[(SCHEDULE_STANDARD, "Padrão (Seg-Sex)"), (SCHEDULE_12X36, "Plantão 12x36")], default=SCHEDULE_STANDARD)
        has_lunch_break = BooleanField("Possui intervalo de almoço?")
        arrival = StringField("Chegada Esperada (HH:MM)", validators=[DataRequired()])
        lunch_start = StringField("Início Almoço (HH:MM)")
        lunch_end = StringField("Fim Almoço (HH:MM)")
        departure = StringField("Saída Esperada (HH:MM)", validators=[DataRequired()])
        tolerance = StringField("Tolerância (minutos)", default=str(DEFAULT_TOLERANCE_MINUTES), validators=[DataRequired()])
        submit = SubmitField("Criar Tipo de Jornada")
