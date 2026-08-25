from datetime import date, timedelta
from typing import Tuple

from sqlalchemy import select

from src.domain.model import DailyPonto, Facultativo, Holiday, PontoStatus
from src.service_layer.audit import log_action
from src.service_layer.permissions import ensure_manager


def complete_retroactive_logs(
    uow,
    actor_id: int,
    employee_id: int,
    end_date: date,
    fill_with_schedule: bool,
) -> Tuple[int, int]:
    with uow:
        return _do_complete_retroactive_logs(uow, actor_id, employee_id, end_date, fill_with_schedule)


def _do_complete_retroactive_logs(uow, actor_id, employee_id, end_date, fill_with_schedule):
    ensure_manager(uow, actor_id)

    employee = uow.users.get_user_by_id(employee_id)
    if not employee:
        raise ValueError("Funcionário não encontrado.")

    start_date = employee.profile.start_analysis_date
    if start_date is None:
        start_date = date(2026, 1, 1)

    if end_date < start_date:
        raise ValueError("A data final deve ser posterior à data de início da análise.")

    existing_dates = {p.entry_date for p in employee.time_entries}
    holiday_dates = _mandatory_holidays(uow)
    facultativo_dates = _facultativo_dates(uow)
    vacation_dates = _vacation_dates(employee)
    attestation_dates = _attestation_dates(employee)

    schedule = employee.work_schedule
    created = 0
    skipped = 0
    current = start_date

    while current <= end_date:
        if current in existing_dates:
            skipped += 1
            current += timedelta(days=1)
            continue
        if current in vacation_dates:
            skipped += 1
            current += timedelta(days=1)
            continue
        if current in attestation_dates:
            skipped += 1
            current += timedelta(days=1)
            continue
        if current in holiday_dates:
            skipped += 1
            current += timedelta(days=1)
            continue
        if current in facultativo_dates:
            skipped += 1
            current += timedelta(days=1)
            continue
        if not schedule:
            _add_entry(uow, employee, current, None, fill_with_schedule)
            created += 1
            current += timedelta(days=1)
            continue
        if not schedule.is_work_day(current):
            skipped += 1
            current += timedelta(days=1)
            continue

        _add_entry(uow, employee, current, schedule, fill_with_schedule)
        created += 1
        current += timedelta(days=1)

    log_action(
        uow, actor_id, "RETROACTIVE_LOGS_COMPLETE",
        target_id=employee_id,
        details=f"Período {start_date} a {end_date}; preencher={fill_with_schedule}; criados={created}; ignorados={skipped}",
    )
    return created, skipped


def _add_entry(uow, employee, entry_date, schedule, fill_with_schedule):
    has_lunch_break = schedule.has_lunch_break if schedule else True

    if fill_with_schedule and schedule:
        ponto = DailyPonto(
            user_id=employee.user_id,
            entry_date=entry_date,
            arrival=schedule.expected_arrival,
            lunch_start=schedule.expected_lunch_start,
            lunch_end=schedule.expected_lunch_end,
            departure=schedule.expected_departure,
            status=PontoStatus.ON_TIME,
            has_lunch_break=has_lunch_break,
            notes="Lançamento retroativo (horários da jornada).",
        )
    else:
        ponto = DailyPonto(
            user_id=employee.user_id,
            entry_date=entry_date,
            status=PontoStatus.MISSING,
            has_lunch_break=has_lunch_break,
            location_data="Sistema: Lançamento retroativo (sem horários).",
            notes="Ausência sem registro de ponto (lançamento retroativo).",
        )
    uow.session.add(ponto)
    employee.time_entries.append(ponto)


def _mandatory_holidays(uow):
    holidays = uow.session.execute(select(Holiday)).scalars().all()
    return {h.holiday_date for h in holidays if h.is_mandatory}


def _facultativo_dates(uow):
    facultativos = uow.session.execute(select(Facultativo)).scalars().all()
    covered = set()
    for fac in facultativos:
        day = fac.start_date
        while day <= fac.end_date:
            covered.add(day)
            day += timedelta(days=1)
    return covered


def _vacation_dates(employee):
    dates = set()
    for v in employee.vacations:
        day = v.start_date
        while day <= v.end_date:
            dates.add(day)
            day += timedelta(days=1)
    return dates


def _attestation_dates(employee):
    dates = set()
    for att in employee.attestations:
        day = att.start_date
        while day <= att.end_date:
            dates.add(day)
            day += timedelta(days=1)
    return dates
