from datetime import date, timedelta
from sqlalchemy import select

from src.domain.model import Holiday
from src.service_layer.unit_of_work import AbstractUnitOfWork
from src.service_layer.permissions import ensure_manager
from src.service_layer.audit import log_action
from src.config import (
        EASTER_OFFSET_CARNAVAL,
        EASTER_OFFSET_CORPUS_CHRISTI,
        EASTER_OFFSET_GOOD_FRIDAY,
        FIXED_NATIONAL_HOLIDAYS,
        FIXED_VALADARES_HOLIDAYS,
        HOLIDAY_SEED_YEAR_END,
        HOLIDAY_SEED_YEAR_START,
)

_FIXED_NATIONAL_HOLIDAYS = FIXED_NATIONAL_HOLIDAYS

_FIXED_VALADARES_HOLIDAYS = FIXED_VALADARES_HOLIDAYS

_HOLIDAY_YEARS = range(HOLIDAY_SEED_YEAR_START, HOLIDAY_SEED_YEAR_END)


def add_holiday(uow: AbstractUnitOfWork, manager_id: int, holiday_date: date, description: str, is_mandatory: bool = True):
        with uow:
                _register_holiday(uow, manager_id, holiday_date, description, is_mandatory)


def seed_holidays(uow: AbstractUnitOfWork):
        with uow:
                _seed_holidays(uow)


def mandatory_holidays(uow):
        holidays = uow.session.execute(select(Holiday)).scalars().all()
        return {h.holiday_date for h in holidays if h.is_mandatory}


def _register_holiday(uow, manager_id, holiday_date, description, is_mandatory):
        ensure_manager(uow, manager_id)
        holiday = Holiday(holiday_date=holiday_date, description=description, is_mandatory=is_mandatory)
        uow.session.merge(holiday)
        log_action(uow, manager_id, "ADD_HOLIDAY", target_id=None, details=f"Data: {holiday_date}, Desc: {description}")


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
        holidays.append(_offset_holiday(easter, EASTER_OFFSET_CARNAVAL, "Carnaval"))
        holidays.append(_offset_holiday(easter, EASTER_OFFSET_GOOD_FRIDAY, "Sexta-feira Santa (Paixão de Cristo)"))
        holidays.append(_offset_holiday(easter, EASTER_OFFSET_CORPUS_CHRISTI, "Corpus Christi"))
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