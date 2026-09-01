from datetime import date, time, timedelta

from src.domain.model import Attestation, DailyPonto, PontoStatus
from src.service_layer.unit_of_work import AbstractUnitOfWork
from src.service_layer.permissions import ensure_manager
from src.service_layer.audit import log_action
from src.service_layer.attendance_helpers import (
        _clocked_intervals,
        _daterange,
        _excuse_all_stages,
        _excused_minutes,
        _overlap_minutes,
        _ponto_for,
        _schedule_intervals,
        _validate_period,
)


def add_attestation(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, start_date: date, end_date: date, cid: str = None, start_time: time = None, end_time: time = None):
        with uow:
                _register_attestation(uow, manager_id, employee_id, start_date, end_date, cid, start_time, end_time)


def remove_attestation_day(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, target_date: date):
        with uow:
                _unregister_attestation_day(uow, manager_id, employee_id, target_date)


def _register_attestation(uow, manager_id, employee_id, start_date, end_date, cid, start_time, end_time):
        ensure_manager(uow, manager_id)
        employee = uow.users.get_user_by_id(employee_id)
        if not employee:
                raise ValueError("Employee not found.")
        _validate_period(start_date, end_date, start_time, end_time)
        partial = start_time is not None
        for day in _daterange(start_date, end_date):
                if partial:
                        _apply_partial_attestation(employee, day, cid, start_time, end_time)
                else:
                        _apply_full_day_attestation(employee, day, cid)
        employee.attestations.append(Attestation(
                user_id=employee_id,
                start_date=start_date,
                end_date=end_date,
                cid=cid,
                start_time=start_time,
                end_time=end_time,
        ))
        details = f"CID {cid}, Período: {start_date} até {end_date}"
        if partial:
                details += f", Horário: {start_time} às {end_time}"
        else:
                details += ", Dia inteiro"
        log_action(uow, manager_id, "ADD_ATTESTATION", target_id=employee_id, details=details)


def _unregister_attestation_day(uow, manager_id, employee_id, target_date):
        ensure_manager(uow, manager_id)
        employee = uow.users.get_user_by_id(employee_id)
        if not employee:
                raise ValueError("Employee not found.")
        matching = [att for att in employee.attestations if att.start_date <= target_date <= att.end_date]
        if not matching:
                raise ValueError("Nenhum atestado encontrado para esta data.")
        att = matching[0]
        attestation_detail = f"CID {att.cid}" if att.cid else "sem CID"
        attestation_detail += f", Período: {att.start_date} até {att.end_date}"
        ponto = _ponto_for(employee, target_date)
        if ponto:
                employee.time_entries.remove(ponto)
                uow.session.delete(ponto)
        if att.start_date == att.end_date:
                employee.attestations.remove(att)
                uow.session.delete(att)
        elif target_date == att.start_date:
                att.start_date = target_date + timedelta(days=1)
        elif target_date == att.end_date:
                att.end_date = target_date - timedelta(days=1)
        else:
                new_start = target_date + timedelta(days=1)
                new_end = att.end_date
                att.end_date = target_date - timedelta(days=1)
                employee.attestations.append(Attestation(
                        user_id=employee_id,
                        start_date=new_start,
                        end_date=new_end,
                        cid=att.cid,
                        start_time=att.start_time,
                        end_time=att.end_time,
                ))
        log_action(uow, manager_id, "REMOVE_ATTESTATION_DAY", target_id=employee_id,
                        details=f"Data: {target_date}, Atestado removido ({attestation_detail})")


def _apply_full_day_attestation(employee, day, cid):
        """Full-day attestation: keep the log and dismiss it, documenting the medical certificate."""
        ponto = _ponto_for(employee, day)
        if not ponto:
                ponto = DailyPonto(user_id=employee.user_id, entry_date=day, status=PontoStatus.DISMISSED)
                employee.time_entries.append(ponto)
        ponto.status = PontoStatus.DISMISSED
        ponto.excused_minutes = 0
        _excuse_all_stages(ponto)
        cid_text = f"CID {cid}" if cid else "Atestado médico"
        ponto.manager_notes = f"{cid_text} - Atestado médico (dia inteiro)"


def _apply_partial_attestation(employee, day, cid, start_time, end_time):
        """Partial-day attestation: dismiss the day, crediting the missed interval as worked time."""
        ponto = _ponto_for(employee, day)
        if not ponto:
                ponto = DailyPonto(user_id=employee.user_id, entry_date=day, status=PontoStatus.DISMISSED)
                employee.time_entries.append(ponto)
        ponto.status = PontoStatus.DISMISSED
        _excuse_all_stages(ponto)
        ponto.excused_minutes = _excused_minutes(
                employee.work_schedule, start_time, end_time,
                ponto.arrival, ponto.lunch_start, ponto.lunch_end, ponto.departure,
        )
        ponto.manager_notes = _attestation_note(cid, start_time, end_time)


def _attestation_note(cid, start_time, end_time):
        cid_text = f"CID {cid}" if cid else "Atestado médico"
        return f"{cid_text} - Abono parcial ({start_time} às {end_time})"