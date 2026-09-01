from src.domain.model import Team
from src.service_layer.audit import log_action
from src.service_layer.permissions import ensure_admin_role
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