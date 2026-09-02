from src.domain.model import Accomplishment
from src.service_layer.audit import log_action
from src.service_layer.permissions import managed_team_ids, scoped_team_ids
from src.service_layer.unit_of_work import AbstractUnitOfWork


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


def create_accomplishment(
        uow: AbstractUnitOfWork,
        actor_id: int,
        *,
        team_id: int,
        title: str,
        description: str = None,
        start_date,
        end_date=None,
        achieved_by_user_id: int = None,
) -> Accomplishment:
        with uow:
                _ensure_manager_scope(uow, actor_id, team_id)
                title = (title or "").strip()
                if not title:
                        raise ValueError("O título da conquista é obrigatório.")
                _validate_period(start_date, end_date)
                accomplishment = Accomplishment(
                        team_id=int(team_id),
                        title=title,
                        description=(description or "").strip() or None,
                        start_date=start_date,
                        end_date=end_date,
                        achieved_by_user_id=int(achieved_by_user_id) if achieved_by_user_id else None,
                        created_by=actor_id,
                )
                uow.users.add_accomplishment(accomplishment)
                uow.commit()
                log_action(uow, actor_id, "CREATE_ACCOMPLISHMENT", target_id=accomplishment.accomplishment_id, details=f"Achievement: {title}")
                return accomplishment


def list_accomplishments(uow: AbstractUnitOfWork, actor_id: int) -> list[Accomplishment]:
        """Accomplishments visible to the actor (their team(s))."""
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
                        raise ValueError("Conquista não encontrada.")
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
        achieved_by_user_id: int = None,
        clear_end_date: bool = False,
):
        with uow:
                accomplishment = uow.users.get_accomplishment_by_id(accomplishment_id)
                if not accomplishment:
                        raise ValueError("Conquista não encontrada.")
                _ensure_manager_scope(uow, actor_id, accomplishment.team_id)
                resolved_title = (title or "").strip() if title is not None else None
                if resolved_title is not None and not resolved_title:
                        raise ValueError("O título da conquista é obrigatório.")
                resolved_start = start_date if start_date is not None else accomplishment.start_date
                resolved_end = None if clear_end_date else (end_date if end_date is not None else accomplishment.end_date)
                _validate_period(resolved_start, resolved_end)
                uow.users.update_accomplishment(
                        accomplishment_id,
                        title=resolved_title,
                        description=(description.strip() or None) if description is not None else None,
                        start_date=resolved_start if start_date is not None else None,
                        end_date=resolved_end if (end_date is not None or clear_end_date) else None,
                        achieved_by_user_id=int(achieved_by_user_id) if achieved_by_user_id else None,
                        clear_end_date=clear_end_date,
                )
                uow.commit()
                log_action(uow, actor_id, "UPDATE_ACCOMPLISHMENT", target_id=accomplishment_id, details=f"Achievement {accomplishment_id} editada")


def delete_accomplishment(uow: AbstractUnitOfWork, actor_id: int, accomplishment_id: int):
        with uow:
                accomplishment = uow.users.get_accomplishment_by_id(accomplishment_id)
                if not accomplishment:
                        raise ValueError("Conquista não encontrada.")
                _ensure_manager_scope(uow, actor_id, accomplishment.team_id)
                uow.users.delete_accomplishment(accomplishment_id)
                uow.commit()
                log_action(uow, actor_id, "DELETE_ACCOMPLISHMENT", target_id=accomplishment_id, details=f"Achievement {accomplishment.title}")