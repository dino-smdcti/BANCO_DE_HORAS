from datetime import date, time, timedelta
from typing import Optional, Tuple

from sqlalchemy import select

from src.domain.model import DailyPonto, Facultativo, Holiday, PontoStatus
from src.service_layer.audit import log_action
from src.service_layer.permissions import ensure_manager
from src.config import (
        FALLBACK_ANALYSIS_DATE,
        RETROACTIVE_LOCATION_MISSING,
        RETROACTIVE_NOTE_FILLED,
        RETROACTIVE_NOTE_MANUAL,
        RETROACTIVE_NOTE_SCHEDULE,
        RETROACTIVE_NOTES_AUTO,
)


def complete_retroactive_logs(
    uow,
    actor_id: int,
    employee_id: int,
    end_date: date,
    fill_with_schedule: bool,
    fill_blank_existing: bool = True,
    overwrite_existing: bool = False,
    manual_arrival: Optional[time] = None,
    manual_lunch_start: Optional[time] = None,
    manual_lunch_end: Optional[time] = None,
    manual_departure: Optional[time] = None,
) -> Tuple[int, int, int]:
    with uow:
        return _do_complete_retroactive_logs(
            uow, actor_id, employee_id, end_date, fill_with_schedule,
            fill_blank_existing, overwrite_existing,
            manual_arrival, manual_lunch_start, manual_lunch_end, manual_departure,
        )


def _do_complete_retroactive_logs(
    uow, actor_id, employee_id, end_date, fill_with_schedule,
    fill_blank_existing, overwrite_existing,
    manual_arrival, manual_lunch_start, manual_lunch_end, manual_departure,
):
    ensure_manager(uow, actor_id)

    employee = uow.users.get_user_by_id(employee_id)
    if not employee:
        raise ValueError("Funcionário não encontrado.")

    start_date = employee.profile.start_analysis_date
    if start_date is None:
        start_date = FALLBACK_ANALYSIS_DATE

    if end_date < start_date:
        raise ValueError("A data final deve ser posterior à data de início da análise.")

    existing_by_date = {p.entry_date: p for p in employee.time_entries}
    holiday_dates = _mandatory_holidays(uow)
    facultativo_dates = _facultativo_dates(uow)
    vacation_dates = _vacation_dates(employee)
    attestation_dates = _attestation_dates(employee)

    schedule = employee.work_schedule
    created = 0
    updated = 0
    skipped = 0
    current = start_date

    while current <= end_date:
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

        is_work_day = True
        if schedule and not schedule.is_work_day(current):
            is_work_day = False

        if not is_work_day:
            skipped += 1
            current += timedelta(days=1)
            continue

        existing_ponto = existing_by_date.get(current)
        if existing_ponto:
            is_blank = not existing_ponto.arrival and not existing_ponto.departure
            should_fill = (is_blank and fill_blank_existing) or (not is_blank and overwrite_existing)
            if should_fill and _fill_existing_entry(
                existing_ponto, schedule, fill_with_schedule,
                manual_arrival, manual_lunch_start,
                manual_lunch_end, manual_departure,
            ):
                updated += 1
            else:
                skipped += 1
        else:
            _add_entry(uow, employee, current, schedule, fill_with_schedule,
                       manual_arrival, manual_lunch_start,
                       manual_lunch_end, manual_departure)
            created += 1

        current += timedelta(days=1)

    log_action(
        uow, actor_id, "RETROACTIVE_LOGS_COMPLETE",
        target_id=employee_id,
        details=(
            f"Período {start_date} a {end_date}; preencher_jornada={fill_with_schedule}; "
            f"preencher_brancos={fill_blank_existing}; sobrescrever={overwrite_existing}; "
            f"criados={created}; atualizados={updated}; ignorados={skipped}"
        ),
    )
    return created, updated, skipped


def _resolve_times(schedule, fill_with_schedule,
                   manual_arrival, manual_lunch_start,
                   manual_lunch_end, manual_departure):
    if fill_with_schedule and schedule:
        return (
            schedule.expected_arrival,
            schedule.expected_lunch_start,
            schedule.expected_lunch_end,
            schedule.expected_departure,
        )
    return (
        manual_arrival,
        manual_lunch_start,
        manual_lunch_end,
        manual_departure,
    )


def _fill_existing_entry(ponto, schedule, fill_with_schedule,
                         manual_arrival, manual_lunch_start,
                         manual_lunch_end, manual_departure):
    arrival, lunch_start, lunch_end, departure = _resolve_times(
        schedule, fill_with_schedule,
        manual_arrival, manual_lunch_start,
        manual_lunch_end, manual_departure,
    )

    changed = False
    if arrival:
        ponto.arrival = arrival
        changed = True
    if lunch_start:
        ponto.lunch_start = lunch_start
        changed = True
    if lunch_end:
        ponto.lunch_end = lunch_end
        changed = True
    if departure:
        ponto.departure = departure
        changed = True

    if changed:
        if fill_with_schedule and schedule:
            ponto.status = PontoStatus.ON_TIME
        else:
            ponto.status = PontoStatus.CORRECTED
        ponto.notes = RETROACTIVE_NOTE_FILLED
        ponto.location_data = ""

    return changed


def _add_entry(uow, employee, entry_date, schedule, fill_with_schedule,
               manual_arrival, manual_lunch_start,
               manual_lunch_end, manual_departure):
    has_lunch_break = schedule.has_lunch_break if schedule else True
    arrival, lunch_start, lunch_end, departure = _resolve_times(
        schedule, fill_with_schedule,
        manual_arrival, manual_lunch_start,
        manual_lunch_end, manual_departure,
    )

    if fill_with_schedule and schedule:
        ponto = DailyPonto(
            user_id=employee.user_id,
            entry_date=entry_date,
            arrival=arrival,
            lunch_start=lunch_start,
            lunch_end=lunch_end,
            departure=departure,
            status=PontoStatus.ON_TIME,
            has_lunch_break=has_lunch_break,
            notes=RETROACTIVE_NOTE_SCHEDULE,
        )
    elif arrival or departure:
        ponto = DailyPonto(
            user_id=employee.user_id,
            entry_date=entry_date,
            arrival=arrival,
            lunch_start=lunch_start,
            lunch_end=lunch_end,
            departure=departure,
            status=PontoStatus.CORRECTED,
            has_lunch_break=has_lunch_break,
            notes=RETROACTIVE_NOTE_MANUAL,
        )
    else:
        ponto = DailyPonto(
            user_id=employee.user_id,
            entry_date=entry_date,
            status=PontoStatus.MISSING,
            has_lunch_break=has_lunch_break,
            location_data=RETROACTIVE_LOCATION_MISSING,
            notes=RETROACTIVE_NOTES_AUTO,
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
