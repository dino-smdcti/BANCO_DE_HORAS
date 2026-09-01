from datetime import date, timedelta

from src.domain.model import DailyPonto, PontoStatus, Vacation
from src.service_layer.unit_of_work import AbstractUnitOfWork
from src.service_layer.permissions import ensure_manager, ensure_managed_user
from src.service_layer.audit import log_action
from src.service_layer.attendance_helpers import _daterange, _excuse_all_stages, _ponto_for, _reset_all_excuses
from src.config import MANAGER_NOTES_VACATION


def add_vacation(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, start_date: date, end_date: date):
        with uow:
                _register_vacation(uow, manager_id, employee_id, start_date, end_date)


def remove_vacation_day(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, target_date: date):
        with uow:
                _unregister_vacation_day(uow, manager_id, employee_id, target_date)


def _unregister_vacation_day(uow, manager_id, employee_id, target_date):
        ensure_manager(uow, manager_id)
        ensure_managed_user(uow, manager_id, employee_id)
        employee = uow.users.get_user_by_id(employee_id)
        if not employee:
                raise ValueError("Employee not found.")
        ponto = _ponto_for(employee, target_date)
        if not ponto:
                raise ValueError("Registro não encontrado.")
        ponto.status = PontoStatus.LATE if (ponto.arrival and ponto.arrival_late) else (PontoStatus.ON_TIME if ponto.arrival else PontoStatus.MISSING)
        ponto.manager_notes = None
        ponto.excused_minutes = 0
        _reset_all_excuses(ponto)
        _split_vacation_record(uow, employee, target_date)
        log_action(uow, manager_id, "REMOVE_VACATION_DAY", target_id=employee_id, details=f"Data: {target_date}")


def _split_vacation_record(uow, employee, target_date):
        matching = [v for v in employee.vacations if v.start_date <= target_date <= v.end_date]
        for vac in matching:
                if vac.start_date == target_date and vac.end_date == target_date:
                        employee.vacations.remove(vac)
                        uow.session.delete(vac)
                elif vac.start_date == target_date:
                        vac.start_date = target_date + timedelta(days=1)
                elif vac.end_date == target_date:
                        vac.end_date = target_date - timedelta(days=1)
                else:
                        old_end = vac.end_date
                        vac.end_date = target_date - timedelta(days=1)
                        employee.vacations.append(Vacation(user_id=employee.user_id, start_date=target_date + timedelta(days=1), end_date=old_end))


def _register_vacation(uow, manager_id, employee_id, start_date, end_date):
        ensure_manager(uow, manager_id)
        ensure_managed_user(uow, manager_id, employee_id)
        employee = uow.users.get_user_by_id(employee_id)
        if not employee:
                raise ValueError("Employee not found.")
        for day in _daterange(start_date, end_date):
                _apply_vacation_day(employee, day)
        employee.vacations.append(Vacation(user_id=employee_id, start_date=start_date, end_date=end_date))
        log_action(uow, manager_id, "ADD_VACATION", target_id=employee_id, details=f"Início: {start_date}, Fim: {end_date}")


def _apply_vacation_day(employee, day):
        """Keep (or create) the day's log as DISMISSED so férias days are visible in the records."""
        ponto = _ponto_for(employee, day)
        if not ponto:
                ponto = DailyPonto(user_id=employee.user_id, entry_date=day, status=PontoStatus.DISMISSED)
                employee.time_entries.append(ponto)
        ponto.status = PontoStatus.DISMISSED
        ponto.excused_minutes = 0
        _excuse_all_stages(ponto)
        ponto.manager_notes = MANAGER_NOTES_VACATION