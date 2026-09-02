"""Internal patch-notes / release board (workforce vertical A6).

Managers and admins publish change notes; every authenticated user can read
them. Publishing a note queues an in-app notification for all users.
"""
from src.domain.model import ChangeLogNote
from src.service_layer.audit import log_action
from src.service_layer.notifications import add_notification
from src.service_layer.permissions import ensure_manager
from src.service_layer.unit_of_work import AbstractUnitOfWork

CHANGELOG_CATEGORIES = ["feature", "fix", "config"]


def create_changelog_note(
        uow: AbstractUnitOfWork, actor_id: int, *, version_or_date: str, title: str, description: str = None, category: str = "feature"
) -> ChangeLogNote:
        with uow:
                ensure_manager(uow, actor_id)
                version_or_date = (version_or_date or "").strip()
                title = (title or "").strip()
                if not version_or_date or not title:
                        raise ValueError("Versão/data e título são obrigatórios.")
                category = (category or "feature").strip().lower()
                if category not in CHANGELOG_CATEGORIES:
                        category = "feature"
                note = ChangeLogNote(
                        version_or_date=version_or_date,
                        title=title,
                        description=(description or "").strip() or None,
                        category=category,
                        created_by=actor_id,
                )
                uow.users.add_changelog_note(note)
                uow.commit()
                log_action(uow, actor_id, "CREATE_CHANGELOG", target_id=note.changelog_id, details=f"Nota: {title}")
                _notify_all(uow, title)
                return note


def list_changelog_notes(uow: AbstractUnitOfWork, actor_id: int) -> list:
        with uow:
                return uow.users.list_changelog_notes()


def delete_changelog_note(uow: AbstractUnitOfWork, actor_id: int, changelog_id: int):
        with uow:
                ensure_manager(uow, actor_id)
                note = uow.users.get_changelog_note_by_id(changelog_id)
                if not note:
                        raise ValueError("Nota não encontrada.")
                uow.users.delete_changelog_note(changelog_id)
                uow.commit()
                log_action(uow, actor_id, "DELETE_CHANGELOG", target_id=changelog_id, details="Nota excluída")


def _notify_all(uow, title: str):
        for user in uow.users.list_all():
                add_notification(uow, user.user_id, f"Nova nota de versão: {title}")
