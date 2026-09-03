from src.domain.model import Kudos, TeamEvent, WikiArticle
from src.service_layer.audit import log_action
from src.service_layer.notifications import add_notification
from src.service_layer.permissions import managed_team_ids, scoped_team_ids
from src.service_layer.unit_of_work import AbstractUnitOfWork

PUBLIC_TEAM_ID = None  # team_id None => public wiki article


def _scoped_team_ids(uow, actor_id) -> set[int]:
        return set(scoped_team_ids(uow, actor_id))


def _ensure_scope(uow, actor_id, team_id):
        if team_id is None:
                return
        if int(team_id) not in _scoped_team_ids(uow, actor_id):
                raise PermissionError("Ação restrita ao seu time.")


def _ensure_write_scope(uow, actor_id, team_id):
        if team_id is None:
                return
        if int(team_id) not in set(managed_team_ids(uow, actor_id)):
                raise PermissionError("Ação restrita ao seu time.")


# ---------------------------------------------------------------------------
# Wiki
# ---------------------------------------------------------------------------

def create_wiki_article(
        uow: AbstractUnitOfWork, actor_id: int, *, title: str, body: str, team_id=None
) -> WikiArticle:
        with uow:
                _ensure_scope(uow, actor_id, team_id)
                title = (title or "").strip()
                body = (body or "").strip()
                if not title or not body:
                        raise ValueError("Título e conteúdo são obrigatórios.")
                article = WikiArticle(title=title, body=body, author_id=actor_id, team_id=int(team_id) if team_id else None)
                uow.users.add_wiki_article(article)
                uow.commit()
                log_action(uow, actor_id, "CREATE_WIKI", target_id=article.wiki_article_id, details=f"Wiki: {title}")
                return article


def list_wiki_articles(uow: AbstractUnitOfWork, actor_id: int) -> list[WikiArticle]:
        with uow:
                visible = _scoped_team_ids(uow, actor_id)
                result: list[WikiArticle] = []
                for team_id in visible:
                        result.extend(uow.users.list_wiki_articles(team_id))
                result.extend(uow.users.list_wiki_articles(PUBLIC_TEAM_ID))
                return result


def update_wiki_article(uow: AbstractUnitOfWork, actor_id: int, wiki_article_id: int, *, title: str = None, body: str = None):
        with uow:
                article = uow.users.get_wiki_article_by_id(wiki_article_id)
                if not article:
                        raise ValueError("Artigo não encontrado.")
                _ensure_scope(uow, actor_id, article.team_id)
                uow.users.update_wiki_article(
                        wiki_article_id,
                        title=title,
                        body=body,
                )
                uow.commit()
                log_action(uow, actor_id, "UPDATE_WIKI", target_id=wiki_article_id, details="Wiki editada")


def delete_wiki_article(uow: AbstractUnitOfWork, actor_id: int, wiki_article_id: int):
        with uow:
                article = uow.users.get_wiki_article_by_id(wiki_article_id)
                if not article:
                        raise ValueError("Artigo não encontrado.")
                _ensure_scope(uow, actor_id, article.team_id)
                if article.author_id != actor_id:
                        _ensure_write_scope(uow, actor_id, article.team_id)
                uow.users.delete_wiki_article(wiki_article_id)
                uow.commit()
                log_action(uow, actor_id, "DELETE_WIKI", target_id=wiki_article_id, details="Wiki excluída")


# ---------------------------------------------------------------------------
# Kudos
# ---------------------------------------------------------------------------

def give_kudo(uow: AbstractUnitOfWork, actor_id: int, *, team_id: int, receiver_id: int, message: str) -> Kudos:
        with uow:
                _ensure_scope(uow, actor_id, team_id)
                receiver_id = int(receiver_id)
                if actor_id == receiver_id:
                        raise ValueError("Você não pode se reconhecer.")
                if not uow.users.get_user_by_id(receiver_id):
                        raise ValueError("Usuário não encontrado.")
                message = (message or "").strip()
                if not message:
                        raise ValueError("A mensagem é obrigatória.")
                kudo = Kudos(team_id=int(team_id), giver_id=actor_id, receiver_id=receiver_id, message=message)
                uow.users.add_kudo(kudo)
                uow.commit()
                log_action(uow, actor_id, "GIVE_KUDO", target_id=receiver_id, details="Kudos enviado")
                add_notification(uow, receiver_id, "Você recebeu um kudos no seu time.")
                return kudo


def list_kudos(uow: AbstractUnitOfWork, actor_id: int) -> list[Kudos]:
        with uow:
                result: list[Kudos] = []
                for team_id in _scoped_team_ids(uow, actor_id):
                        result.extend(uow.users.list_kudos_by_team(team_id))
                return result


def delete_kudo(uow: AbstractUnitOfWork, actor_id: int, kudo_id: int):
        with uow:
                for team_id in _scoped_team_ids(uow, actor_id):
                        for candidate in uow.users.list_kudos_by_team(team_id):
                                if candidate.kudo_id != kudo_id:
                                        continue
                                if candidate.giver_id != actor_id:
                                        _ensure_write_scope(uow, actor_id, candidate.team_id)
                                uow.users.delete_kudo(kudo_id)
                                uow.commit()
                                log_action(uow, actor_id, "DELETE_KUDO", target_id=kudo_id, details="Kudos excluído")
                                return
                raise ValueError("Kudos não encontrado.")


# ---------------------------------------------------------------------------
# Team events
# ---------------------------------------------------------------------------

def create_team_event(
        uow: AbstractUnitOfWork, actor_id: int, *, team_id: int, title: str, date, description: str = None
) -> TeamEvent:
        with uow:
                _ensure_write_scope(uow, actor_id, team_id)
                title = (title or "").strip()
                if not title:
                        raise ValueError("O título do evento é obrigatório.")
                if not date:
                        raise ValueError("A data do evento é obrigatória.")
                event = TeamEvent(team_id=int(team_id), title=title, date=date, description=(description or "").strip() or None)
                uow.users.add_team_event(event)
                uow.commit()
                log_action(uow, actor_id, "CREATE_TEAM_EVENT", target_id=event.event_id, details=f"Evento: {title}")
                return event


def list_team_events(uow: AbstractUnitOfWork, actor_id: int) -> list[TeamEvent]:
        with uow:
                result: list[TeamEvent] = []
                for team_id in _scoped_team_ids(uow, actor_id):
                        result.extend(uow.users.list_team_events_by_team(team_id))
                return result


def delete_team_event(uow: AbstractUnitOfWork, actor_id: int, event_id: int):
        with uow:
                event = uow.users.get_team_event_by_id(event_id)
                if not event:
                        raise ValueError("Evento não encontrado.")
                _ensure_write_scope(uow, actor_id, event.team_id)
                uow.users.delete_team_event(event_id)
                uow.commit()
                log_action(uow, actor_id, "DELETE_TEAM_EVENT", target_id=event_id, details="Evento excluído")