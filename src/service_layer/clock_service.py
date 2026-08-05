from datetime import datetime, time, timedelta, timezone
from typing import List, Optional
from sqlalchemy import select

from src.domain.model import DailyPonto, CorrectionRequest, PontoStatus, UserRole
from src.domain.time_utils import limit_after, limit_before
from src.service_layer.unit_of_work import AbstractUnitOfWork
from src.service_layer.permissions import ensure_manager, ensure_not_self
from src.service_layer.notifications import add_notification
from src.service_layer.audit import log_action

_STAGE_MESSAGES = {
        "arrival": "Chegada registrada",
        "lunch_start": "Saída para almoço registrada",
        "lunch_end": "Retorno do almoço registrado",
        "departure": "Fim de jornada registrado",
}


def clock_in_out(uow: AbstractUnitOfWork, user_id: int, location: Optional[str] = None, stage: Optional[str] = None, notes: Optional[str] = None) -> str:
        with uow:
                user = _require_user(uow, user_id)
                now_time, today = _brazil_now()
                ponto = _todays_ponto(user, today)
                target_stage = stage or _next_stage(ponto)
                _register_stage(user, ponto, target_stage, now_time, today, location or "Não obtida", notes)
                message = _STAGE_MESSAGES[target_stage]
                log_action(uow, user_id, "CLOCK_EVENT", target_id=user_id, details=f"{message} ({target_stage})")
                return message


def submit_correction_request(uow: AbstractUnitOfWork, user_id: int, ponto_date, stage: str, proposed_time: time):
        with uow:
                request = CorrectionRequest(user_id=user_id, ponto_date=ponto_date, stage=stage, proposed_time=proposed_time)
                uow.session.add(request)
                log_action(uow, user_id, "SUBMIT_CORRECTION_REQUEST", target_id=None, details=f"Data: {ponto_date}, Estágio: {stage}")


def list_pending_corrections(uow: AbstractUnitOfWork, manager_id: int) -> List[CorrectionRequest]:
        with uow:
                ensure_manager(uow, manager_id)
                return uow.session.execute(select(CorrectionRequest).where(CorrectionRequest.status == "pending")).scalars().all()


def review_correction_request(uow: AbstractUnitOfWork, manager_id: int, request_id: int, approved: bool):
        with uow:
                ensure_manager(uow, manager_id)
                request = _find_request(uow, request_id)
                _resolve_request(uow, request, approved, manager_id)
                log_action(uow, manager_id, "REVIEW_CORRECTION_REQUEST", target_id=request.user_id, details=f"ID Pedido: {request_id}, Aprovado: {approved}")


def manual_ponto_correction(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, entry_date, arrival: Optional[time] = None, lunch_start: Optional[time] = None, lunch_end: Optional[time] = None, departure: Optional[time] = None, manager_notes: Optional[str] = None, email_sender=None) -> bool:
        with uow:
                manager = ensure_manager(uow, manager_id)
                ensure_not_self(uow, manager_id, employee_id)
                user = _require_user(uow, employee_id)
                ponto = _ponto_for(user, entry_date)
                return _apply_manual_correction(uow, manager, user, ponto, entry_date, arrival, lunch_start, lunch_end, departure, manager_notes, email_sender)


def delete_ponto_entry(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, entry_date):
        with uow:
                _perform_delete_ponto(uow, manager_id, employee_id, entry_date)


def dismiss_justification(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, entry_date):
        with uow:
                _perform_dismiss(uow, manager_id, employee_id, entry_date)


def review_anomaly_badge(uow: AbstractUnitOfWork, admin_id: int, employee_id: int, entry_date, stage: str, action: str):
        with uow:
                _apply_anomaly_decision(uow, admin_id, employee_id, entry_date, stage, action)


def _require_user(uow, user_id):
        user = uow.users.get_user_by_id(user_id)
        if not user:
                raise ValueError("User not found.")
        return user


def _brazil_now():
        """Current clock in Brasília time (UTC-3)."""
        now = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)
        return now.time(), now.date()


def _todays_ponto(user, today):
        for entry in user.time_entries:
                if entry.entry_date == today:
                        return entry
        return None


def _ponto_for(user, entry_date):
        for entry in user.time_entries:
                if entry.entry_date == entry_date:
                        return entry
        return None


def _next_stage(ponto):
        if not ponto:
                return "arrival"
        if ponto.has_lunch_break and not ponto.lunch_start:
                return "lunch_start"
        if ponto.has_lunch_break and not ponto.lunch_end:
                return "lunch_end"
        if not ponto.departure:
                return "departure"
        raise ValueError("Jornada de hoje já está completa.")


def _register_stage(user, ponto, stage, now_time, today, location, notes):
        if stage == "arrival":
                _register_arrival(user, ponto, now_time, today, location)
        elif stage == "lunch_start":
                _register_lunch_start(user, ponto, now_time, today, location)
        elif stage == "lunch_end":
                _register_lunch_end(user, ponto, now_time, today, location)
        elif stage == "departure":
                _register_departure(user, ponto, now_time, today, location, notes)
        else:
                raise ValueError("Estágio inválido.")


def _register_arrival(user, ponto, now_time, today, location):
        if not ponto:
                ponto = _new_ponto(user, today, now_time)
                user.time_entries.append(ponto)
        else:
                ponto.arrival = now_time
        _log_location(ponto, f"Chegada: {location}")
        _flag_if_arrival_late(ponto, user, today, now_time)


def _register_lunch_start(user, ponto, now_time, today, location):
        _require_ponto(ponto)
        ponto.lunch_start = now_time
        _log_location(ponto, f"Almoço (Sai): {location}")
        _flag_if_lunch_start_late(ponto, user, today, now_time)


def _register_lunch_end(user, ponto, now_time, today, location):
        _require_ponto(ponto)
        ponto.lunch_end = now_time
        _log_location(ponto, f"Almoço (Vol): {location}")
        _flag_if_lunch_end_late(ponto, user, today, now_time)


def _register_departure(user, ponto, now_time, today, location, notes):
        _require_ponto(ponto)
        ponto.departure = now_time
        _log_location(ponto, f"Fim: {location}")
        _flag_if_departure_early(ponto, user, today, now_time)
        if notes:
                ponto.notes = notes


def _new_ponto(user, today, now_time):
        return DailyPonto(user_id=user.user_id, entry_date=today, arrival=now_time, has_lunch_break=_has_lunch_break(user))


def _has_lunch_break(user):
        return user.work_schedule.has_lunch_break if user.work_schedule else True


def _require_ponto(ponto):
        if not ponto:
                raise ValueError("Registro de chegada não encontrado.")


def _log_location(ponto, text):
        if ponto.location_data is None:
                ponto.location_data = ""
        ponto.location_data += f" | {text}"


def _flag_if_arrival_late(ponto, user, today, now_time):
        schedule = user.work_schedule
        if schedule and now_time > limit_after(schedule.expected_arrival, schedule.tolerance_minutes, today):
                ponto.status = PontoStatus.LATE
                ponto.arrival_late = True


def _flag_if_lunch_start_late(ponto, user, today, now_time):
        schedule = user.work_schedule
        if schedule and schedule.expected_lunch_start and now_time < limit_before(schedule.expected_lunch_start, schedule.tolerance_minutes, today):
                ponto.status = PontoStatus.LATE
                ponto.lunch_start_late = True


def _flag_if_lunch_end_late(ponto, user, today, now_time):
        schedule = user.work_schedule
        if schedule and schedule.expected_lunch_end and now_time > limit_after(schedule.expected_lunch_end, schedule.tolerance_minutes, today):
                ponto.status = PontoStatus.LATE
                ponto.lunch_end_late = True


def _flag_if_departure_early(ponto, user, today, now_time):
        schedule = user.work_schedule
        if schedule and now_time < limit_before(schedule.expected_departure, schedule.tolerance_minutes, today):
                ponto.status = PontoStatus.LATE
                ponto.departure_early = True


def _find_request(uow, request_id):
        request = uow.session.execute(select(CorrectionRequest).where(CorrectionRequest.request_id == request_id)).scalar_one_or_none()
        if not request:
                raise ValueError("Solicitação não encontrada.")
        return request


def _resolve_request(uow, request, approved, manager_id):
        if approved:
                _approve_request(uow, request, manager_id)
        else:
                _reject_request(uow, request)


def _approve_request(uow, request, manager_id):
        request.status = "approved"
        user = _require_user(uow, request.user_id)
        ponto = _ponto_for(user, request.ponto_date)
        if not ponto:
                ponto = _new_ponto(user, request.ponto_date, None)
                user.time_entries.append(ponto)
        _apply_proposed_times(ponto, request)
        _mark_reviewed(ponto)
        if user.work_schedule:
                _re_evaluate_anomalies(ponto, user.work_schedule, request.ponto_date)
        ponto.status = PontoStatus.CORRECTED
        _log_location(ponto, f"Corrigido via solicitação aprovada por gestor {manager_id}")
        add_notification(uow, request.user_id, f"Sua solicitação de correção para {request.ponto_date} foi APROVADA.")


def _reject_request(uow, request):
        request.status = "rejected"
        add_notification(uow, request.user_id, f"Sua solicitação de correção para {request.ponto_date} foi REJEITADA.")


def _apply_proposed_times(ponto, request):
        if request.stage == "arrival":
                ponto.arrival = request.proposed_time
        elif request.stage == "lunch_start":
                ponto.lunch_start = request.proposed_time
        elif request.stage == "lunch_end":
                ponto.lunch_end = request.proposed_time
        elif request.stage == "departure":
                ponto.departure = request.proposed_time


def _mark_reviewed(ponto):
        ponto.arrival_late_reviewed = True
        ponto.lunch_start_late_reviewed = True
        ponto.lunch_end_late_reviewed = True
        ponto.departure_early_reviewed = True


def _re_evaluate_anomalies(ponto, schedule, day):
        ponto.arrival_late = _is_late_arrival(ponto.arrival, schedule, day)
        ponto.lunch_start_late = _is_early_lunch_start(ponto.lunch_start, schedule, day)
        ponto.lunch_end_late = _is_late_lunch_end(ponto.lunch_end, schedule, day)
        ponto.departure_early = _is_early_departure(ponto.departure, schedule, day)


def _is_late_arrival(arrival, schedule, day):
        return bool(arrival) and arrival > limit_after(schedule.expected_arrival, schedule.tolerance_minutes, day)


def _is_early_lunch_start(lunch_start, schedule, day):
        if not lunch_start or not schedule.expected_lunch_start:
                return False
        return lunch_start < limit_before(schedule.expected_lunch_start, schedule.tolerance_minutes, day)


def _is_late_lunch_end(lunch_end, schedule, day):
        if not lunch_end or not schedule.expected_lunch_end:
                return False
        return lunch_end > limit_after(schedule.expected_lunch_end, schedule.tolerance_minutes, day)


def _is_early_departure(departure, schedule, day):
        return bool(departure) and departure < limit_before(schedule.expected_departure, schedule.tolerance_minutes, day)


def _apply_manual_correction(uow, manager, user, ponto, entry_date, arrival, lunch_start, lunch_end, departure, manager_notes, email_sender):
        if not ponto and not any([arrival, lunch_start, lunch_end, departure]):
                return False
        if not ponto:
                ponto = _create_ponto(user, entry_date)
        if not _update_times(ponto, arrival, lunch_start, lunch_end, departure, manager_notes):
                return False
        ponto.status = PontoStatus.CORRECTED
        _mark_reviewed(ponto)
        manager_name = manager.profile.full_name or manager.email
        _log_location(ponto, f"Corrigido manualmente por Gestor: {manager_name}")
        add_notification(uow, user.user_id, f"Seu ponto de {entry_date} foi corrigido manualmente pelo gestor {manager_name}.", email_sender=email_sender)
        log_action(uow, manager.user_id, "MANUAL_CORRECTION", target_id=user.user_id, details=f"Data: {entry_date}")
        return True


def _create_ponto(user, entry_date):
        ponto = DailyPonto(user_id=user.user_id, entry_date=entry_date, has_lunch_break=_has_lunch_break(user))
        user.time_entries.append(ponto)
        return ponto


def _update_times(ponto, arrival, lunch_start, lunch_end, departure, manager_notes):
        changed = _set_if_changed(ponto, "arrival", arrival)
        changed |= _set_if_changed(ponto, "lunch_start", lunch_start)
        changed |= _set_if_changed(ponto, "lunch_end", lunch_end)
        changed |= _set_if_changed(ponto, "departure", departure)
        if manager_notes is not None and ponto.manager_notes != manager_notes:
                ponto.manager_notes = manager_notes
                changed = True
        return changed


def _set_if_changed(ponto, attribute, value):
        if getattr(ponto, attribute) != value:
                setattr(ponto, attribute, value)
                return True
        return False


def _perform_delete_ponto(uow, manager_id, employee_id, entry_date):
        manager = ensure_manager(uow, manager_id)
        ensure_not_self(uow, manager_id, employee_id)
        user = _require_user(uow, employee_id)
        matching = [entry for entry in user.time_entries if entry.entry_date == entry_date]
        if not matching:
                return
        for entry in matching:
                user.time_entries.remove(entry)
                uow.session.delete(entry)
        manager_name = manager.profile.full_name or manager.email
        log_action(uow, manager_id, "DELETE_PONTO", target_id=employee_id, details=f"Excluído(s) {len(matching)} registro(s) para {entry_date} por {manager_name}")


def _perform_dismiss(uow, manager_id, employee_id, entry_date):
        ensure_manager(uow, manager_id)
        user = _require_user(uow, employee_id)
        ponto = _ponto_for(user, entry_date)
        if not ponto:
                raise ValueError("Registro não encontrado.")
        ponto.status = PontoStatus.DISMISSED
        log_action(uow, manager_id, "DISMISS_JUSTIFICATION", target_id=employee_id, details=f"Data: {entry_date}")


def _apply_anomaly_decision(uow, admin_id, employee_id, entry_date, stage, action):
        admin = uow.users.get_user_by_id(admin_id)
        if not admin or admin.role != UserRole.ADMIN:
                raise PermissionError("Apenas o Administrador pode aprovar anomalias individuais.")
        user = _require_user(uow, employee_id)
        ponto = _ponto_for(user, entry_date)
        if not ponto:
                raise ValueError("Registro não encontrado.")
        _decide_anomaly(ponto, stage, action)
        log_action(uow, admin_id, f"{action.upper()}_ANOMALY", target_id=employee_id, details=f"Data: {entry_date}, Estágio: {stage}")


_ANOMALY_DECISIONS = {
        "arrival": ("arrival_late_reviewed", "arrival_late_approved", "arrival_late_excused"),
        "lunch_start": ("lunch_start_late_reviewed", "lunch_start_late_approved", "lunch_start_late_excused"),
        "lunch_end": ("lunch_end_late_reviewed", "lunch_end_late_approved", "lunch_end_late_excused"),
        "departure": ("departure_early_reviewed", "departure_early_approved", "departure_early_excused"),
        "missing": ("missing_reviewed", "missing_approved", "missing_excused"),
}


def _decide_anomaly(ponto, stage, action):
        reviewed, approved, excused = _ANOMALY_DECISIONS[stage]
        setattr(ponto, reviewed, True)
        if action == "approve":
                setattr(ponto, approved, True)
        elif action == "excuse":
                setattr(ponto, excused, True)
