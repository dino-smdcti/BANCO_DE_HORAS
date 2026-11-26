from datetime import date

from src.domain.model import Accomplishment
from src.service_layer.audit import log_action
from src.service_layer.permissions import managed_team_ids, scoped_team_ids
from src.service_layer.unit_of_work import AbstractUnitOfWork

META_STATUS_EM_ANDAMENTO = "em_andamento"
META_STATUS_ATINGIDA = "atingida"
META_STATUS_ATRASADA = "atrasada"

META_STATUS_LABELS = {
    META_STATUS_EM_ANDAMENTO: "Em andamento",
    META_STATUS_ATINGIDA: "Atingida",
    META_STATUS_ATRASADA: "Atrasada",
}


def meta_status(accomplishment: Accomplishment, today: date = None) -> str:
        """Derive a goal's status from its end date and target date."""
        today = today or date.today()
        if accomplishment.end_date:
                return META_STATUS_ATINGIDA
        if accomplishment.target_date and accomplishment.target_date < today:
                return META_STATUS_ATRASADA
        return META_STATUS_EM_ANDAMENTO


def _ensure_manager_scope(uow: AbstractUnitOfWork, actor_id: int, team_id) -> set[int]:
        teams = set(managed_team_ids(uow, actor_id))
        if int(team_id) not in teams:
                raise PermissionError("Ação restrita ao seu time.")
        return teams


def _validate_period(start_date, end_date):
        if not start_date:
                raise ValueError("A data de início é obrigatória.")
        if end_date and end_date < start_date:
                raise ValueError("O fim do período não pode ser antes do início.")


def _parse_points(value) -> int:
        try:
                points = int(value or 0)
        except (TypeError, ValueError):
                points = 0
        return max(0, points)


def create_accomplishment(
        uow: AbstractUnitOfWork,
        actor_id: int,
        *,
        team_id: int,
        title: str,
        description: str = None,
        start_date,
        end_date=None,
        target_date=None,
        points=0,
        achieved_by_user_id: int = None,
) -> Accomplishment:
        with uow:
                _ensure_manager_scope(uow, actor_id, team_id)
                title = (title or "").strip()
                if not title:
                        raise ValueError("O título da meta é obrigatório.")
                _validate_period(start_date, end_date)
                accomplishment = Accomplishment(
                        team_id=int(team_id),
                        title=title,
                        description=(description or "").strip() or None,
                        start_date=start_date,
                        end_date=end_date,
                        target_date=target_date,
                        points=_parse_points(points),
                        achieved_by_user_id=int(achieved_by_user_id) if achieved_by_user_id else None,
                        created_by=actor_id,
                )
                uow.users.add_accomplishment(accomplishment)
                uow.commit()
                log_action(uow, actor_id, "CREATE_ACCOMPLISHMENT", target_id=accomplishment.accomplishment_id, details=f"Meta: {title}")
                return accomplishment


def list_accomplishments(uow: AbstractUnitOfWork, actor_id: int) -> list[Accomplishment]:
        """Goals visible to the actor (their team(s))."""
        with uow:
                visible_team_ids = set(scoped_team_ids(uow, actor_id))
                result: list[Accomplishment] = []
                for team_id in visible_team_ids:
                        result.extend(uow.users.list_accomplishments_by_team(team_id))
                return result


def get_accomplishment(uow: AbstractUnitOfWork, actor_id: int, accomplishment_id: int) -> Accomplishment:
        with uow:
                accomplishment = uow.users.get_accomplishment_by_id(accomplishment_id)
                if not accomplishment:
                        raise ValueError("Meta não encontrada.")
                visible_team_ids = set(scoped_team_ids(uow, actor_id))
                if accomplishment.team_id not in visible_team_ids:
                        raise PermissionError("Ação restrita ao seu time.")
                return accomplishment


def edit_accomplishment(
        uow: AbstractUnitOfWork,
        actor_id: int,
        accomplishment_id: int,
        *,
        title: str = None,
        description: str = None,
        start_date=None,
        end_date=None,
        target_date=None,
        points: int = None,
        achieved_by_user_id: int = None,
        clear_end_date: bool = False,
        clear_target_date: bool = False,
):
        with uow:
                accomplishment = uow.users.get_accomplishment_by_id(accomplishment_id)
                if not accomplishment:
                        raise ValueError("Meta não encontrada.")
                _ensure_manager_scope(uow, actor_id, accomplishment.team_id)
                resolved_title = (title or "").strip() if title is not None else None
                if resolved_title is not None and not resolved_title:
                        raise ValueError("O título da meta é obrigatório.")
                resolved_start = start_date if start_date is not None else accomplishment.start_date
                resolved_end = None if clear_end_date else (end_date if end_date is not None else accomplishment.end_date)
                _validate_period(resolved_start, resolved_end)
                uow.users.update_accomplishment(
                        accomplishment_id,
                        title=resolved_title,
                        description=(description.strip() or None) if description is not None else None,
                        start_date=resolved_start if start_date is not None else None,
                        end_date=resolved_end if (end_date is not None or clear_end_date) else None,
                        target_date=None if clear_target_date else target_date,
                        points=_parse_points(points) if points is not None else None,
                        achieved_by_user_id=int(achieved_by_user_id) if achieved_by_user_id else None,
                        clear_end_date=clear_end_date,
                        clear_target_date=clear_target_date,
                )
                uow.commit()
                log_action(uow, actor_id, "UPDATE_ACCOMPLISHMENT", target_id=accomplishment_id, details=f"Meta {accomplishment_id} editada")


def delete_accomplishment(uow: AbstractUnitOfWork, actor_id: int, accomplishment_id: int):
        with uow:
                accomplishment = uow.users.get_accomplishment_by_id(accomplishment_id)
                if not accomplishment:
                        raise ValueError("Meta não encontrada.")
                _ensure_manager_scope(uow, actor_id, accomplishment.team_id)
                uow.users.delete_accomplishment(accomplishment_id)
                uow.commit()
                log_action(uow, actor_id, "DELETE_ACCOMPLISHMENT", target_id=accomplishment_id, details=f"Meta {accomplishment.title}")


def meta_leaderboard(uow: AbstractUnitOfWork, actor_id: int) -> list[dict]:
        """Sum points by the person who achieved each concluded goal, in scope."""
        with uow:
                totals: dict[int, int] = {}
                for accomplishment in list_accomplishments(uow, actor_id):
                        if accomplishment.end_date and accomplishment.achieved_by_user_id:
                                totals[accomplishment.achieved_by_user_id] = (
                                        totals.get(accomplishment.achieved_by_user_id, 0) + accomplishment.points
                                )
                users = uow.users.list_all()
                labels = {u.user_id: (u.profile.full_name or u.email) for u in users}
                rows = [
                        {"name": labels.get(uid, "—"), "points": points}
                        for uid, points in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
                ]
                return rows
