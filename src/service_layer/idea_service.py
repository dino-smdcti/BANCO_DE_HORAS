from src.config import (
        IDEA_CATEGORIES,
        IDEA_CATEGORY_KAIZEN,
        IDEA_STATUSES,
        IDEA_STATUS_IMPLEMENTED,
)
from src.domain.model import Idea, IdeaVote
from src.service_layer.audit import log_action
from src.service_layer.notifications import add_notification
from src.service_layer.permissions import managed_team_ids, scoped_team_ids
from src.service_layer.unit_of_work import AbstractUnitOfWork


def _idea_team_permitted(uow: AbstractUnitOfWork, actor_id: int, idea: Idea) -> bool:
        """Idea visibility: own team(s) for everyone; managers can also govern it."""
        return idea.team_id in set(scoped_team_ids(uow, actor_id))


def create_idea(
        uow: AbstractUnitOfWork,
        actor_id: int,
        *,
        team_id: int,
        title: str,
        category: str = None,
        description: str = None,
) -> Idea:
        with uow:
                team_id = int(team_id)
                if team_id not in set(scoped_team_ids(uow, actor_id)):
                        raise PermissionError("Ação restrita ao seu time.")
                title = (title or "").strip()
                if not title:
                        raise ValueError("O título da ideia é obrigatório.")
                category = (category or "").strip() or "idea"
                if category not in IDEA_CATEGORIES:
                        category = IDEA_CATEGORY_KAIZEN if "kaizen" in category.lower() else "idea"
                idea = Idea(
                        team_id=team_id,
                        title=title,
                        author_user_id=actor_id,
                        category=category,
                        description=(description or "").strip() or None,
                )
                uow.users.add_idea(idea)
                uow.commit()
                log_action(uow, actor_id, "CREATE_IDEA", target_id=idea.idea_id, details=f"Idea: {title}")
                return idea


def list_ideas(uow: AbstractUnitOfWork, actor_id: int, category: str = None) -> list[Idea]:
        """Ideas visible to the actor, optionally filtered by category (idea|kaizen)."""
        with uow:
                visible_team_ids = set(scoped_team_ids(uow, actor_id))
                result: list[Idea] = []
                for team_id in visible_team_ids:
                        result.extend(uow.users.list_ideas_by_team(team_id))
                if category:
                        result = [idea for idea in result if idea.category == category]
                return result


def get_idea(uow: AbstractUnitOfWork, actor_id: int, idea_id: int) -> Idea:
        with uow:
                idea = uow.users.get_idea_by_id(idea_id)
                if not idea:
                        raise ValueError("Ideia não encontrada.")
                if not _idea_team_permitted(uow, actor_id, idea):
                        raise PermissionError("Ação restrita ao seu time.")
                return idea


def vote_idea(uow: AbstractUnitOfWork, actor_id: int, idea_id: int) -> bool:
        """Toggle the actor's vote on an idea. Returns True if voted, False if unvoted."""
        with uow:
                idea = uow.users.get_idea_by_id(idea_id)
                if not idea:
                        raise ValueError("Ideia não encontrada.")
                if not _idea_team_permitted(uow, actor_id, idea):
                        raise PermissionError("Ação restrita ao seu time.")
                existing = uow.users.get_idea_vote(idea_id, actor_id)
                if existing:
                        uow.users.delete_idea_vote(existing.vote_id)
                        uow.commit()
                        return False
                uow.users.add_idea_vote(IdeaVote(idea_id=idea_id, voter_user_id=actor_id))
                uow.commit()
                log_action(uow, actor_id, "VOTE_IDEA", target_id=idea_id, details=f"Vote on idea {idea_id}")
                return True


def set_idea_status(
        uow: AbstractUnitOfWork,
        actor_id: int,
        idea_id: int,
        status: str,
        *,
        review_date=None,
        review_owner: str = None,
) -> None:
        with uow:
                idea = uow.users.get_idea_by_id(idea_id)
                if not idea:
                        raise ValueError("Ideia não encontrada.")
                if idea.team_id not in set(managed_team_ids(uow, actor_id)):
                        raise PermissionError("Ação restrita ao seu time.")
                status = (status or "").strip()
                if status not in IDEA_STATUSES:
                        raise ValueError("Status inválido.")
                is_implemented = status == IDEA_STATUS_IMPLEMENTED
                resolved_review = None
                if is_implemented:
                        resolved_review = review_date if review_date is not None else idea.review_date
                uow.users.update_idea(
                        idea_id,
                        status=status,
                        review_date=resolved_review,
                        review_owner=(review_owner or "").strip() or None,
                )
                uow.commit()
                log_action(uow, actor_id, "UPDATE_IDEA_STATUS", target_id=idea_id, details=f"Idea {idea_id} -> {status}")
                add_notification(uow, idea.author_user_id, f"Sua ideia foi atualizada: {idea.title} (status: {status}).")


def delete_idea(uow: AbstractUnitOfWork, actor_id: int, idea_id: int) -> None:
        with uow:
                idea = uow.users.get_idea_by_id(idea_id)
                if not idea:
                        raise ValueError("Ideia não encontrada.")
                if idea.author_user_id == actor_id:
                        uow.users.delete_idea(idea_id)
                        uow.commit()
                        log_action(uow, actor_id, "DELETE_IDEA", target_id=idea_id, details=f"Idea: {idea.title}")
                        return
                if idea.team_id not in set(managed_team_ids(uow, actor_id)):
                        raise PermissionError("Ação restrita ao seu time.")
                uow.users.delete_idea(idea_id)
                uow.commit()
                log_action(uow, actor_id, "DELETE_IDEA", target_id=idea_id, details=f"Idea: {idea.title}")