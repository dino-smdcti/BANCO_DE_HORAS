"""Pre-approval clock requests.

An employee asks their superior in advance to accept a late arrival / early
departure (or another clock stage) on a specific day. Once approved, the clock
service auto-excuses the corresponding anomaly instead of flagging it, so the
employee does not need to justify afterwards.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select

from src.domain.model import ClockRequest, User, UserRole
from src.service_layer.audit import log_action
from src.service_layer.notifications import add_notification
from src.service_layer.unit_of_work import AbstractUnitOfWork
from src.config import (
        CORRECTION_STATUS_APPROVED,
        CORRECTION_STATUS_PENDING,
        CORRECTION_STATUS_REJECTED,
        STAGE_ARRIVAL,
        STAGE_DEPARTURE,
        STAGE_LUNCH_END,
        STAGE_LUNCH_START,
)

_VALID_STAGES = (STAGE_ARRIVAL, STAGE_LUNCH_START, STAGE_LUNCH_END, STAGE_DEPARTURE)


def get_superior_id(uow: AbstractUnitOfWork, user_id: int) -> Optional[int]:
        """Resolve the employee's superior (team lead) or a manager's admin."""
        user = uow.users.get_user_by_id(user_id)
        if not user:
                return None
        if user.role == UserRole.EMPLOYEE:
                if not user.team_id:
                        return None
                team = uow.users.get_team_by_id(user.team_id)
                return team.lead_user_id if team else None
        if user.role in (UserRole.MANAGER, UserRole.GESTOR):
                admin = uow.session.execute(
                        select(User).where(User.role == UserRole.ADMIN).order_by(User.user_id)
                ).scalars().first()
                return admin.user_id if admin else None
        return None


def create_clock_request(
        uow: AbstractUnitOfWork,
        user_id: int,
        entry_date,
        stage: str,
        direction: str,
        proposed_time,
        reason: Optional[str] = None,
) -> ClockRequest:
        with uow:
                user = uow.users.get_user_by_id(user_id)
                if not user:
                        raise ValueError("Usuário não encontrado.")
                if user.role == UserRole.ADMIN:
                        raise ValueError("O secretário não precisa solicitar ajuste de ponto.")
                if stage not in _VALID_STAGES:
                        raise ValueError("Estágio inválido.")
                superior_id = get_superior_id(uow, user_id)
                if not superior_id:
                        raise ValueError("Nenhum superior foi encontrado para este usuário.")
                request = ClockRequest(
                        user_id=user_id,
                        superior_id=superior_id,
                        entry_date=entry_date,
                        stage=stage,
                        direction=direction,
                        proposed_time=proposed_time,
                        reason=reason,
                )
                uow.session.add(request)
                log_action(uow, user_id, "SUBMIT_CLOCK_REQUEST", target_id=superior_id, details=f"Data: {entry_date}, Estágio: {stage}, Direção: {direction}")
                return request


def list_clock_requests_for_superior(uow: AbstractUnitOfWork, superior_id: int) -> List[ClockRequest]:
        with uow:
                return uow.session.execute(
                        select(ClockRequest)
                        .where(ClockRequest.superior_id == superior_id)
                        .order_by(ClockRequest.created_at.desc())
                ).scalars().all()


def list_clock_requests_for_user(uow: AbstractUnitOfWork, user_id: int) -> List[ClockRequest]:
        with uow:
                return uow.session.execute(
                        select(ClockRequest)
                        .where(ClockRequest.user_id == user_id)
                        .order_by(ClockRequest.created_at.desc())
                ).scalars().all()


def list_all_clock_requests(uow: AbstractUnitOfWork) -> List[ClockRequest]:
        with uow:
                return uow.session.execute(
                        select(ClockRequest).order_by(ClockRequest.created_at.desc())
                ).scalars().all()


def review_clock_request(
        uow: AbstractUnitOfWork,
        superior_id: int,
        request_id: int,
        approved: bool,
        reviewer_notes: Optional[str] = None,
) -> None:
        with uow:
                request = uow.session.execute(
                        select(ClockRequest).where(ClockRequest.request_id == request_id)
                ).scalar_one_or_none()
                if not request:
                        raise ValueError("Solicitação não encontrada.")
                if request.superior_id != superior_id:
                        raise PermissionError("Você não pode revisar esta solicitação.")
                if request.status != CORRECTION_STATUS_PENDING:
                        raise ValueError("Esta solicitação já foi processada.")

                if approved:
                        request.status = CORRECTION_STATUS_APPROVED
                        add_notification(uow, request.user_id, f"Sua solicitação de ajuste de ponto para {request.entry_date} foi APROVADA.")
                else:
                        if not reviewer_notes:
                                raise ValueError("É obrigatório informar o motivo da rejeição.")
                        request.status = CORRECTION_STATUS_REJECTED
                        request.reviewer_notes = reviewer_notes
                        add_notification(uow, request.user_id, f"Sua solicitação de ajuste de ponto para {request.entry_date} foi REJEITADA. Motivo: {reviewer_notes}")
                request.reviewed_at = datetime.now()
                log_action(uow, superior_id, "REVIEW_CLOCK_REQUEST", target_id=request.user_id, details=f"ID: {request_id}, Aprovado: {approved}")


def has_approved_clock_request(uow: AbstractUnitOfWork, user_id: int, entry_date, stage: str) -> bool:
        request = uow.session.execute(
                select(ClockRequest).where(
                        ClockRequest.user_id == user_id,
                        ClockRequest.entry_date == entry_date,
                        ClockRequest.stage == stage,
                        ClockRequest.status == CORRECTION_STATUS_APPROVED,
                )
        ).scalar_one_or_none()
        return request is not None
