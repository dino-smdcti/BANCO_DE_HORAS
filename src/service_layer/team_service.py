from src.domain.model import Team
from src.service_layer.audit import log_action
from src.service_layer.permissions import managed_team_ids, ensure_admin_role
from src.service_layer.unit_of_work import AbstractUnitOfWork


def create_team(uow: AbstractUnitOfWork, admin_id: int, name: str, secretariat: str = None) -> Team:
        with uow:
                ensure_admin_role(uow, admin_id)
                name = (name or "").strip()
                if not name:
                        raise ValueError("O nome do time é obrigatório.")
                if uow.users.get_team_by_name(name):
                        raise ValueError("Já existe um time com este nome.")
                team = Team(name=name, secretariat=((secretariat or "").strip() or None))
                uow.users.add_team(team)
                uow.commit()
                log_action(uow, admin_id, "CREATE_TEAM", target_id=team.team_id, details=f"Time: {name}")
                return team


def list_teams(uow: AbstractUnitOfWork):
        with uow:
                return uow.users.list_teams()


def list_team_members(uow: AbstractUnitOfWork, team_id: int):
        with uow:
                return uow.users.list_users_by_team(team_id)


def assign_user_team(uow: AbstractUnitOfWork, admin_id: int, user_id: int, team_id):
        with uow:
                ensure_admin_role(uow, admin_id)
                user = uow.users.get_user_by_id(user_id)
                if not user:
                        raise ValueError("Usuário não encontrado.")
                resolved_team_id = int(team_id) if team_id else None
                if resolved_team_id and not uow.users.get_team_by_id(resolved_team_id):
                        raise ValueError("Time não encontrado.")
                uow.users.set_user_team(user.user_id, resolved_team_id)
                uow.commit()
                log_action(uow, admin_id, "ASSIGN_USER_TEAM", target_id=user.user_id, details=f"User: {user.email}, Team ID: {resolved_team_id}")


def update_team(uow: AbstractUnitOfWork, admin_id: int, team_id: int, *, name: str = None, secretariat: str = None, lead_user_id=None):
        with uow:
                ensure_admin_role(uow, admin_id)
                _apply_team_update(uow, admin_id, team_id, name=name, secretariat=secretariat, lead_user_id=lead_user_id)


def scoped_update_team(uow: AbstractUnitOfWork, actor_id: int, team_id: int, *, name: str = None, secretariat: str = None, lead_user_id=None):
        """Team update scoped to the actor's management teams (ADMIN/GESTOR any; MANAGER own)."""
        with uow:
                if team_id not in set(managed_team_ids(uow, actor_id)):
                        raise PermissionError("Ação restrita ao seu time.")
                _apply_team_update(uow, actor_id, team_id, name=name, secretariat=secretariat, lead_user_id=lead_user_id)


def _apply_team_update(uow, actor_id, team_id, *, name, secretariat, lead_user_id):
        team = uow.users.get_team_by_id(team_id)
        if not team:
                raise ValueError("Time não encontrado.")
        resolved_name = (name or "").strip() if name is not None else None
        if resolved_name is not None:
                if not resolved_name:
                        raise ValueError("O nome do time é obrigatório.")
                existing = uow.users.get_team_by_name(resolved_name)
                if existing and existing.team_id != team_id:
                        raise ValueError("Já existe um time com este nome.")
        resolved_lead = int(lead_user_id) if lead_user_id else None
        if resolved_lead and not uow.users.get_user_by_id(resolved_lead):
                raise ValueError("Líder não encontrado.")
        effective_lead = resolved_lead if lead_user_id else None
        uow.users.update_team(
                team_id,
                name=resolved_name,
                secretariat=((secretariat or "").strip() or None) if secretariat is not None else None,
                lead_user_id=effective_lead,
                clear_lead=(lead_user_id == "" or lead_user_id is None),
        )
        uow.commit()
        log_action(uow, actor_id, "UPDATE_TEAM", target_id=team_id, details=f"Time {team_id} atualizado")


def clear_team_lead(uow: AbstractUnitOfWork, admin_id: int, team_id: int):
        with uow:
                if not uow.users.get_team_by_id(team_id):
                        raise ValueError("Time não encontrado.")
                uow.users.update_team(team_id, clear_lead=True)
                uow.commit()
                log_action(uow, admin_id, "UPDATE_TEAM", target_id=team_id, details=f"Time {team_id} sem líder")


def team_rollups(uow: AbstractUnitOfWork, team_ids=None) -> dict:
        """Aggregate counts per team for the team dashboard: members, open tasks,
        open ideas, and recent accomplishments. When team_ids is None, aggregates
        every team."""
        with uow:
                teams = uow.users.list_teams() if team_ids is None else [uow.users.get_team_by_id(t) for t in team_ids]
                result = {}
                for team in teams:
                        if not team:
                                continue
                        result[team.team_id] = {
                                "name": team.name,
                                "secretariat": team.secretariat,
                                "lead_user_id": team.lead_user_id,
                                "members": uow.users.count_team_members(team.team_id),
                                "open_tasks": uow.users.count_open_tasks_by_team(team.team_id),
                                "open_ideas": uow.users.count_open_ideas_by_team(team.team_id),
                                "accomplishments": uow.users.list_accomplishments_by_team(team.team_id),
                        }
                return result