from datetime import date, time
from sqlalchemy import select

from src.domain.model import Facultativo, PontoStatus
from src.service_layer.unit_of_work import AbstractUnitOfWork
from src.service_layer.permissions import ensure_manager
from src.service_layer.audit import log_action
from src.service_layer.attendance_helpers import _daterange, _excuse_all_stages, _excused_minutes, _ponto_for, _validate_period


def add_facultativo(uow: AbstractUnitOfWork, manager_id: int, start_date: date, end_date: date, description: str = "", start_time: time = None, end_time: time = None):
        with uow:
                _register_facultativo(uow, manager_id, start_date, end_date, description, start_time, end_time)


def facultativo_records(uow):
        return uow.session.execute(select(Facultativo)).scalars().all()


def _register_facultativo(uow, manager_id, start_date, end_date, description, start_time, end_time):
        ensure_manager(uow, manager_id)
        _validate_period(start_date, end_date, start_time, end_time)
        partial = start_time is not None
        for employee in uow.users.list_employees():
                for day in _daterange(start_date, end_date):
                        _apply_facultativo_day(employee, day, description, start_time, end_time)
        uow.session.add(Facultativo(
                start_date=start_date,
                end_date=end_date,
                description=description,
                start_time=start_time,
                end_time=end_time,
        ))
        details = f"Desc: {description or 'Ponto facultativo'}, Período: {start_date} até {end_date}"
        if partial:
                details += f", Horário: {start_time} às {end_time}"
        else:
                details += ", Dia inteiro"
        log_action(uow, manager_id, "ADD_FACULTATIVO", target_id=None, details=details)


def _apply_facultativo_day(employee, day, description, start_time, end_time):
        """Dismiss a day's log for a facultativo period (only touches existing entries)."""
        ponto = _ponto_for(employee, day)
        if not ponto:
                return
        ponto.status = PontoStatus.DISMISSED
        _excuse_all_stages(ponto)
        if start_time is not None:
                ponto.excused_minutes = _excused_minutes(
                        employee.work_schedule, start_time, end_time,
                        ponto.arrival, ponto.lunch_start, ponto.lunch_end, ponto.departure,
                )
                ponto.manager_notes = f"Ponto facultativo ({description or 'sem descrição'}) - {start_time} às {end_time}"
        else:
                ponto.excused_minutes = 0
                ponto.manager_notes = f"Ponto facultativo ({description or 'sem descrição'}) - Dia inteiro"