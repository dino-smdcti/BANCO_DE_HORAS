from datetime import date
from sqlalchemy import select

from src.domain.model import CompanySettings
from src.service_layer.unit_of_work import AbstractUnitOfWork
from src.config import FALLBACK_ANALYSIS_DATE


def get_start_analysis_date(uow: AbstractUnitOfWork) -> date:
        with uow:
                settings = uow.session.execute(select(CompanySettings)).scalar_one_or_none()
                return settings.start_analysis_date if settings else FALLBACK_ANALYSIS_DATE