from datetime import date, time, timedelta
from sqlalchemy import select

from src.domain.model import DailyPonto, Holiday, PontoStatus, Vacation, CompanySettings, Attestation, Facultativo
from src.domain.time_utils import minutes_between
from src.service_layer.unit_of_work import AbstractUnitOfWork
from src.service_layer.permissions import ensure_manager
from src.service_layer.audit import log_action

_FIXED_NATIONAL_HOLIDAYS = [
        (1, 1, "Confraternização Universal (Ano Novo)"),
        (4, 21, "Tiradentes"),
        (5, 1, "Dia do Trabalhador"),
        (9, 7, "Independência do Brasil"),
        (10, 12, "Nossa Senhora Aparecida (Padroeira do Brasil)"),
        (11, 2, "Finados"),
        (11, 15, "Proclamação da República"),
        (11, 20, "Dia Nacional de Zumbi e da Consciência Negra"),
        (12, 25, "Natal"),
]

_FIXED_VALADARES_HOLIDAYS = [
        (1, 30, "Aniversário de Governador Valadares"),
        (6, 13, "Santo Antônio (Padroeiro de Governador Valadares)"),
]

_HOLIDAY_YEARS = range(2025, 2036)


def add_vacation(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, start_date: date, end_date: date):
        with uow:
                _register_vacation(uow, manager_id, employee_id, start_date, end_date)


def add_holiday(uow: AbstractUnitOfWork, manager_id: int, holiday_date: date, description: str, is_mandatory: bool = True):
        with uow:
                _register_holiday(uow, manager_id, holiday_date, description, is_mandatory)


def add_attestation(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, start_date: date, end_date: date, cid: str = None, start_time: time = None, end_time: time = None):
        with uow:
                _register_attestation(uow, manager_id, employee_id, start_date, end_date, cid, start_time, end_time)


def remove_attestation_day(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, target_date: date):
        with uow:
                _unregister_attestation_day(uow, manager_id, employee_id, target_date)


def remove_vacation_day(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, target_date: date):
        with uow:
                _unregister_vacation_day(uow, manager_id, employee_id, target_date)


def remove_missing_excuse(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, target_date: date):
        with uow:
                _unregister_missing_excuse(uow, manager_id, employee_id, target_date)


def add_facultativo(uow: AbstractUnitOfWork, manager_id: int, start_date: date, end_date: date, description: str = "", start_time: time = None, end_time: time = None):
        with uow:
                _register_facultativo(uow, manager_id, start_date, end_date, description, start_time, end_time)


def seed_holidays(uow: AbstractUnitOfWork):
        with uow:
                _seed_holidays(uow)


def get_start_analysis_date(uow: AbstractUnitOfWork) -> date:
        with uow:
                settings = uow.session.execute(select(CompanySettings)).scalar_one_or_none()
                return settings.start_analysis_date if settings else date(2026, 1, 1)


def _unregister_vacation_day(uow, manager_id, employee_id, target_date):
        ensure_manager(uow, manager_id)
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


def _unregister_missing_excuse(uow, manager_id, employee_id, target_date):
        ensure_manager(uow, manager_id)
        employee = uow.users.get_user_by_id(employee_id)
        if not employee:
                raise ValueError("Employee not found.")
        ponto = _ponto_for(employee, target_date)
        if not ponto:
                raise ValueError("Registro não encontrado.")
        ponto.missing_reviewed = False
        ponto.missing_approved = False
        ponto.missing_excused = False
        log_action(uow, manager_id, "REMOVE_MISSING_EXCUSE", target_id=employee_id, details=f"Data: {target_date}")


def _reset_all_excuses(ponto):
        for reviewed, approved, excused in _ANOMALY_FLAG_TRIPLES:
                setattr(ponto, reviewed, False)
                setattr(ponto, approved, False)
                setattr(ponto, excused, False)
        ponto.missing_reviewed = False
        ponto.missing_approved = False
        ponto.missing_excused = False


def _register_vacation(uow, manager_id, employee_id, start_date, end_date):
        ensure_manager(uow, manager_id)
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
        ponto.manager_notes = "Férias"


def _register_holiday(uow, manager_id, holiday_date, description, is_mandatory):
        ensure_manager(uow, manager_id)
        holiday = Holiday(holiday_date=holiday_date, description=description, is_mandatory=is_mandatory)
        uow.session.merge(holiday)
        log_action(uow, manager_id, "ADD_HOLIDAY", target_id=None, details=f"Data: {holiday_date}, Desc: {description}")


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


def _validate_period(start_date, end_date, start_time, end_time):
        if end_date < start_date:
                raise ValueError("Período inválido.")
        partial = start_time is not None or end_time is not None
        if partial and (start_time is None or end_time is None):
                raise ValueError("Informe o horário de início e fim.")
        if partial and end_time <= start_time:
                raise ValueError("Horário inválido.")


def _daterange(start_date, end_date):
        day = start_date
        while day <= end_date:
                yield day
                day += timedelta(days=1)


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


def _ponto_for(employee, day):
        for entry in employee.time_entries:
                if entry.entry_date == day:
                        return entry
        return None


def _excuse_all_stages(ponto):
        for reviewed, approved, excused in _ANOMALY_FLAG_TRIPLES:
                setattr(ponto, reviewed, True)
                setattr(ponto, excused, True)
        setattr(ponto, "missing_reviewed", True)
        setattr(ponto, "missing_excused", True)


_ANOMALY_FLAG_TRIPLES = [
        ("arrival_late_reviewed", "arrival_late_approved", "arrival_late_excused"),
        ("lunch_start_late_reviewed", "lunch_start_late_approved", "lunch_start_late_excused"),
        ("lunch_end_late_reviewed", "lunch_end_late_approved", "lunch_end_late_excused"),
        ("departure_early_reviewed", "departure_early_approved", "departure_early_excused"),
]


def _attestation_note(cid, start_time, end_time):
        cid_text = f"CID {cid}" if cid else "Atestado médico"
        return f"{cid_text} - Abono parcial ({start_time} às {end_time})"


def _excused_minutes(schedule, start_time, end_time, arrival, lunch_start, lunch_end, departure):
        """Minutes of the interval that fall inside the expected workday but were not actually worked."""
        if not schedule:
                return 0
        expected = _schedule_intervals(schedule)
        clocked = _clocked_intervals(arrival, lunch_start, lunch_end, departure, schedule.has_lunch_break)
        total = sum(_overlap_minutes(start_time, end_time, a, b) for a, b in expected)
        worked = sum(_overlap_minutes(start_time, end_time, a, b) for a, b in clocked)
        return max(0, total - worked)


def _schedule_intervals(schedule):
        if schedule.has_lunch_break and schedule.expected_lunch_start and schedule.expected_lunch_end:
                return [
                        (schedule.expected_arrival, schedule.expected_lunch_start),
                        (schedule.expected_lunch_end, schedule.expected_departure),
                ]
        return [(schedule.expected_arrival, schedule.expected_departure)]


def _clocked_intervals(arrival, lunch_start, lunch_end, departure, has_lunch_break):
        if has_lunch_break and lunch_start and lunch_end:
                intervals = []
                if arrival:
                        intervals.append((arrival, lunch_start))
                if departure:
                        intervals.append((lunch_end, departure))
                return intervals
        if arrival and departure:
                return [(arrival, departure)]
        return []


def _overlap_minutes(s1, e1, s2, e2):
        start = max(s1, s2)
        end = min(e1, e2)
        if end <= start:
                return 0
        return minutes_between(start, end)


def _seed_holidays(uow):
        """Prepopulate Brazilian national holidays plus Governador Valadares regional holidays."""
        for year in _HOLIDAY_YEARS:
                for holiday in _holidays_for_year(year):
                        uow.session.merge(holiday)
        uow.commit()


def _holidays_for_year(year):
        holidays = [_fixed_holiday(month, day, description, year) for month, day, description in _FIXED_NATIONAL_HOLIDAYS]
        holidays += [_fixed_holiday(month, day, description, year) for month, day, description in _FIXED_VALADARES_HOLIDAYS]
        easter = _easter_date(year)
        holidays.append(_offset_holiday(easter, -47, "Carnaval"))
        holidays.append(_offset_holiday(easter, -2, "Sexta-feira Santa (Paixão de Cristo)"))
        holidays.append(_offset_holiday(easter, 60, "Corpus Christi"))
        return holidays


def _fixed_holiday(month, day, description, year):
        return Holiday(holiday_date=date(year, month, day), description=description, is_mandatory=True)


def _offset_holiday(base_date, day_offset, description):
        return Holiday(holiday_date=base_date + timedelta(days=day_offset), description=description, is_mandatory=True)


def _easter_date(year):
        """Anonymous Gregorian algorithm for Easter Sunday."""
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        return date(year, month, day)
