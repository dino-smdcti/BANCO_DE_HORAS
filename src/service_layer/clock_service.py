from datetime import datetime, time, timedelta, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.domain.model import DailyPonto, CorrectionRequest, PontoStatus, UserRole
from src.domain.time_utils import limit_after, limit_before
from src.service_layer.unit_of_work import AbstractUnitOfWork
from src.service_layer.permissions import ensure_manager, ensure_not_self, ensure_managed_user
from src.service_layer.notifications import add_notification
from src.service_layer.audit import log_action
from src.service_layer.attendance_helpers import _ponto_for, _require_user
from src.service_layer.clock_request_service import has_approved_clock_request
from src.config import (
        ANOMALY_ACTION_APPROVE,
        ANOMALY_ACTION_EXCUSE,
        ANOMALY_DECISION_FLAGS,
        BRAZIL_UTC_OFFSET_HOURS,
        CLOCK_LOCATION_NA,
        CORRECTION_STATUS_APPROVED,
        CORRECTION_STATUS_PENDING,
        CORRECTION_STATUS_REJECTED,
        LOCATION_PREFIX_ARRIVAL,
        LOCATION_PREFIX_DEPARTURE,
        LOCATION_PREFIX_LUNCH_END,
        LOCATION_PREFIX_LUNCH_START,
        LOCATION_SEPARATOR,
        STAGE_ARRIVAL,
        STAGE_DEPARTURE,
        STAGE_LUNCH_END,
        STAGE_LUNCH_START,
        STAGE_MISSING,
        STAGE_READY_MESSAGES,
)

_STAGE_MESSAGES = STAGE_READY_MESSAGES


def clock_in_out(uow: AbstractUnitOfWork, user_id: int, location: Optional[str] = None, stage: Optional[str] = None, notes: Optional[str] = None) -> str:
        with uow:
                try:
                        user = _require_user(uow, user_id)
                        now_time, today = _brazil_now()
                        ponto = _todays_ponto(user, today)
                        target_stage = stage or _next_stage(ponto)
                        _register_stage(uow, user, ponto, target_stage, now_time, today, location or CLOCK_LOCATION_NA, notes)
                        message = _STAGE_MESSAGES[target_stage]
                        log_action(uow, user_id, "CLOCK_EVENT", target_id=user_id, details=f"{message} ({target_stage})")
                except IntegrityError:
                        uow.rollback()
                        raise ValueError("Registro do dia já existe.")
                return message


def submit_correction_request(uow: AbstractUnitOfWork, user_id: int, ponto_date, stage: str, proposed_time: time):
        with uow:
                request = CorrectionRequest(user_id=user_id, ponto_date=ponto_date, stage=stage, proposed_time=proposed_time)
                uow.session.add(request)
                log_action(uow, user_id, "SUBMIT_CORRECTION_REQUEST", target_id=None, details=f"Data: {ponto_date}, Estágio: {stage}")


def list_pending_corrections(uow: AbstractUnitOfWork, manager_id: int) -> List[CorrectionRequest]:
        with uow:
                manager = ensure_manager(uow, manager_id)
                requests = uow.session.execute(select(CorrectionRequest).where(CorrectionRequest.status == CORRECTION_STATUS_PENDING)).scalars().all()
                if manager.role in [UserRole.ADMIN, UserRole.GESTOR]:
                        return requests
                if not manager.team_id:
                        return []
                team_ids = set(uow.users.list_user_ids_by_team(manager.team_id))
                return [request for request in requests if request.user_id in team_ids]


def review_correction_request(uow: AbstractUnitOfWork, manager_id: int, request_id: int, approved: bool):
        with uow:
                ensure_manager(uow, manager_id)
                request = _find_request(uow, request_id)
                ensure_managed_user(uow, manager_id, request.user_id)
                _resolve_request(uow, request, approved, manager_id)
                log_action(uow, manager_id, "REVIEW_CORRECTION_REQUEST", target_id=request.user_id, details=f"ID Pedido: {request_id}, Aprovado: {approved}")


def manual_ponto_correction(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, entry_date, arrival: Optional[time] = None, lunch_start: Optional[time] = None, lunch_end: Optional[time] = None, departure: Optional[time] = None, manager_notes: Optional[str] = None, email_sender=None) -> bool:
        with uow:
                manager = ensure_manager(uow, manager_id)
                ensure_not_self(uow, manager_id, employee_id)
                ensure_managed_user(uow, manager_id, employee_id)
                user = _require_user(uow, employee_id)
                ponto = _ponto_for(user, entry_date)
                return _apply_manual_correction(uow, manager, user, ponto, entry_date, arrival, lunch_start, lunch_end, departure, manager_notes, email_sender)


def delete_ponto_entry(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, entry_date):
        with uow:
                _perform_delete_ponto(uow, manager_id, employee_id, entry_date)


def dismiss_justification(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, entry_date):
        with uow:
                _perform_dismiss(uow, manager_id, employee_id, entry_date)


def submit_justification(uow: AbstractUnitOfWork, user_id: int, entry_date, justification: str):
        """Employee submits a justification for an anomalous day (late/missing).

        The justification is stored for the manager to review; the day's status is
        left untouched until the manager approves or rejects it.
        """
        with uow:
                user = _require_user(uow, user_id)
                ponto = _ponto_for(user, entry_date)
                if not ponto:
                        raise ValueError("Registro não encontrado.")
                if not justification or not justification.strip():
                        raise ValueError("A justificativa é obrigatória.")
                ponto.justification = justification.strip()
                log_action(uow, user_id, "SUBMIT_JUSTIFICATION", target_id=user_id, details=f"Data: {entry_date}")


def review_justification(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, entry_date, approved: bool, email_sender=None):
        """Manager approves (JUSTIFIED) or rejects (LATE/REJECTED) an employee's justification."""
        with uow:
                ensure_manager(uow, manager_id)
                ensure_managed_user(uow, manager_id, employee_id)
                user = _require_user(uow, employee_id)
                ponto = _ponto_for(user, entry_date)
                if not ponto:
                        raise ValueError("Registro não encontrado.")
                if approved:
                        ponto.status = PontoStatus.JUSTIFIED
                        add_notification(uow, employee_id, f"Sua justificativa para {entry_date} foi APROVADA.", email_sender=email_sender)
                else:
                        has_late = ponto.arrival_late or ponto.lunch_start_late or ponto.lunch_end_late or ponto.departure_early or ponto.lunch_start_early
                        ponto.status = PontoStatus.LATE if has_late else PontoStatus.REJECTED
                        ponto.justification = None
                        add_notification(uow, employee_id, f"Sua justificativa para {entry_date} foi REJEITADA.", email_sender=email_sender)
                log_action(uow, manager_id, "REVIEW_JUSTIFICATION", target_id=employee_id, details=f"Data: {entry_date}, Aprovado: {approved}")



def remove_missing_excuse(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, target_date):
        with uow:
                _unregister_missing_excuse(uow, manager_id, employee_id, target_date)


def review_anomaly_badge(uow: AbstractUnitOfWork, admin_id: int, employee_id: int, entry_date, stage: str, action: str):
        with uow:
                _apply_anomaly_decision(uow, admin_id, employee_id, entry_date, stage, action)


def _brazil_now():
        """Current clock in Brasília time (UTC-3)."""
        now = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=BRAZIL_UTC_OFFSET_HOURS)
        return now.time(), now.date()


def _todays_ponto(user, today):
        for entry in user.time_entries:
                if entry.entry_date == today:
                        return entry
        return None


def _next_stage(ponto):
        if not ponto:
                return STAGE_ARRIVAL
        if ponto.has_lunch_break and not ponto.lunch_start:
                return STAGE_LUNCH_START
        if ponto.has_lunch_break and not ponto.lunch_end:
                return STAGE_LUNCH_END
        if not ponto.departure:
                return STAGE_DEPARTURE
        raise ValueError("Jornada de hoje já está completa.")


def _register_stage(uow, user, ponto, stage, now_time, today, location, notes):
        # Any registerable stage may start the day's log; a late arrival (or an
        # explicit manual POST) must not block later stages on an absent Chegada.
        if not ponto:
                ponto = _emit_ponto(user, today)
                user.time_entries.append(ponto)
        if stage == STAGE_ARRIVAL:
                _register_arrival(uow, user, ponto, now_time, today, location)
        elif stage == STAGE_LUNCH_START:
                _register_lunch_start(uow, user, ponto, now_time, today, location)
        elif stage == STAGE_LUNCH_END:
                _register_lunch_end(uow, user, ponto, now_time, today, location)
        elif stage == STAGE_DEPARTURE:
                _register_departure(uow, user, ponto, now_time, today, location, notes)
        else:
                raise ValueError("Estágio inválido.")


def _register_arrival(uow, user, ponto, now_time, today, location):
        ponto.arrival = now_time
        _log_location(ponto, f"{LOCATION_PREFIX_ARRIVAL}: {location}")
        _flag_if_arrival_late(uow, ponto, user, today, now_time)


def _register_lunch_start(uow, user, ponto, now_time, today, location):
        ponto.lunch_start = now_time
        _log_location(ponto, f"{LOCATION_PREFIX_LUNCH_START}: {location}")
        _flag_if_lunch_start_late(uow, ponto, user, today, now_time)
        _flag_if_lunch_start_early(uow, ponto, user, today, now_time)


def _register_lunch_end(uow, user, ponto, now_time, today, location):
        ponto.lunch_end = now_time
        _log_location(ponto, f"{LOCATION_PREFIX_LUNCH_END}: {location}")
        _flag_if_lunch_end_late(uow, ponto, user, today, now_time)


def _register_departure(uow, user, ponto, now_time, today, location, notes):
        ponto.departure = now_time
        _log_location(ponto, f"{LOCATION_PREFIX_DEPARTURE}: {location}")
        _flag_if_departure_early(uow, ponto, user, today, now_time)
        if notes:
                ponto.notes = notes


def _new_ponto(user, today, now_time):
        return DailyPonto(user_id=user.user_id, entry_date=today, arrival=now_time, has_lunch_break=_has_lunch_break(user))


def _emit_ponto(user, today):
        """Create a day's log without fixing an arrival time.

        Used when a later stage (lunch/departure) starts the day, e.g. after a
        missing or never-registered arrival, so we don't fabricate one.
        """
        return DailyPonto(user_id=user.user_id, entry_date=today, arrival=None, has_lunch_break=_has_lunch_break(user))


def _has_lunch_break(user):
        return user.work_schedule.has_lunch_break if user.work_schedule else True


def _log_location(ponto, text):
        if ponto.location_data is None:
                ponto.location_data = ""
        ponto.location_data += f"{LOCATION_SEPARATOR}{text}"


def _flag_if_arrival_late(uow, ponto, user, today, now_time):
        schedule = user.work_schedule
        if schedule and now_time > limit_after(schedule.expected_arrival, schedule.tolerance_minutes, today):
                if uow is not None and has_approved_clock_request(uow, user.user_id, today, STAGE_ARRIVAL):
                        ponto.arrival_late_approved = True
                else:
                        ponto.status = PontoStatus.LATE
                        ponto.arrival_late = True


def _flag_if_lunch_start_late(uow, ponto, user, today, now_time):
        schedule = user.work_schedule
        if schedule and schedule.expected_lunch_start and now_time > limit_after(schedule.expected_lunch_start, schedule.tolerance_minutes, today):
                if uow is not None and has_approved_clock_request(uow, user.user_id, today, STAGE_LUNCH_START):
                        ponto.lunch_start_late_approved = True
                else:
                        ponto.status = PontoStatus.LATE
                        ponto.lunch_start_late = True


def _flag_if_lunch_start_early(uow, ponto, user, today, now_time):
        schedule = user.work_schedule
        if schedule and schedule.expected_lunch_start and now_time < limit_before(schedule.expected_lunch_start, schedule.tolerance_minutes, today):
                if uow is not None and has_approved_clock_request(uow, user.user_id, today, STAGE_LUNCH_START):
                        ponto.lunch_start_early_approved = True
                else:
                        ponto.status = PontoStatus.LATE
                        ponto.lunch_start_early = True


def _flag_if_lunch_end_late(uow, ponto, user, today, now_time):
        schedule = user.work_schedule
        if schedule and schedule.expected_lunch_end and now_time > limit_after(schedule.expected_lunch_end, schedule.tolerance_minutes, today):
                if uow is not None and has_approved_clock_request(uow, user.user_id, today, STAGE_LUNCH_END):
                        ponto.lunch_end_late_approved = True
                else:
                        ponto.status = PontoStatus.LATE
                        ponto.lunch_end_late = True


def _flag_if_departure_early(uow, ponto, user, today, now_time):
        schedule = user.work_schedule
        if schedule and now_time < limit_before(schedule.expected_departure, schedule.tolerance_minutes, today):
                if uow is not None and has_approved_clock_request(uow, user.user_id, today, STAGE_DEPARTURE):
                        ponto.departure_early_approved = True
                else:
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
        request.status = CORRECTION_STATUS_APPROVED
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
        request.status = CORRECTION_STATUS_REJECTED
        add_notification(uow, request.user_id, f"Sua solicitação de correção para {request.ponto_date} foi REJEITADA.")


def _apply_proposed_times(ponto, request):
        if request.stage == STAGE_ARRIVAL:
                ponto.arrival = request.proposed_time
        elif request.stage == STAGE_LUNCH_START:
                ponto.lunch_start = request.proposed_time
        elif request.stage == STAGE_LUNCH_END:
                ponto.lunch_end = request.proposed_time
        elif request.stage == STAGE_DEPARTURE:
                ponto.departure = request.proposed_time
        else:
                raise ValueError(f"Estágio de correção desconhecido: {request.stage}")


def _mark_reviewed(ponto):
        ponto.arrival_late_reviewed = True
        ponto.lunch_start_late_reviewed = True
        ponto.lunch_start_early_reviewed = True
        ponto.lunch_end_late_reviewed = True
        ponto.departure_early_reviewed = True


def _re_evaluate_anomalies(ponto, schedule, day):
        ponto.arrival_late = _is_late_arrival(ponto.arrival, schedule, day)
        ponto.lunch_start_late = _is_late_lunch_start(ponto.lunch_start, schedule, day)
        ponto.lunch_start_early = _is_early_lunch_start(ponto.lunch_start, schedule, day)
        ponto.lunch_end_late = _is_late_lunch_end(ponto.lunch_end, schedule, day)
        ponto.departure_early = _is_early_departure(ponto.departure, schedule, day)


def _is_late_arrival(arrival, schedule, day):
        return bool(arrival) and arrival > limit_after(schedule.expected_arrival, schedule.tolerance_minutes, day)


def _is_late_lunch_start(lunch_start, schedule, day):
        if not lunch_start or not schedule.expected_lunch_start:
                return False
        return lunch_start > limit_after(schedule.expected_lunch_start, schedule.tolerance_minutes, day)


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
        ensure_managed_user(uow, manager_id, employee_id)
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
        ensure_managed_user(uow, manager_id, employee_id)
        user = _require_user(uow, employee_id)
        ponto = _ponto_for(user, entry_date)
        if not ponto:
                raise ValueError("Registro não encontrado.")
        ponto.status = PontoStatus.DISMISSED
        log_action(uow, manager_id, "DISMISS_JUSTIFICATION", target_id=employee_id, details=f"Data: {entry_date}")


def _unregister_missing_excuse(uow, manager_id, employee_id, target_date):
        ensure_manager(uow, manager_id)
        ensure_managed_user(uow, manager_id, employee_id)
        user = _require_user(uow, employee_id)
        ponto = _ponto_for(user, target_date)
        if not ponto:
                raise ValueError("Registro não encontrado.")
        ponto.missing_reviewed = False
        ponto.missing_approved = False
        ponto.missing_excused = False
        log_action(uow, manager_id, "REMOVE_MISSING_EXCUSE", target_id=employee_id, details=f"Data: {target_date}")


def _apply_anomaly_decision(uow, admin_id, employee_id, entry_date, stage, action):
        admin = uow.users.get_user_by_id(admin_id)
        if not admin or admin.role not in [UserRole.ADMIN, UserRole.GESTOR]:
                raise PermissionError("Apenas Administrador ou Gestor pode aprovar anomalias individuais.")
        user = _require_user(uow, employee_id)
        ponto = _ponto_for(user, entry_date)
        if not ponto:
                raise ValueError("Registro não encontrado.")
        _decide_anomaly(ponto, stage, action)
        log_action(uow, admin_id, f"{action.upper()}_ANOMALY", target_id=employee_id, details=f"Data: {entry_date}, Estágio: {stage}")


_ANOMALY_DECISIONS = ANOMALY_DECISION_FLAGS


def _decide_anomaly(ponto, stage, action):
        reviewed, approved, excused = _ANOMALY_DECISIONS[stage]
        setattr(ponto, reviewed, True)
        if action == ANOMALY_ACTION_APPROVE:
                setattr(ponto, approved, True)
        elif action == ANOMALY_ACTION_EXCUSE:
                setattr(ponto, excused, True)
