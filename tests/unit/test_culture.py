from datetime import date

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.domain.model import UserRole
from src.service_layer.culture_service import (
        create_team_event,
        create_wiki_article,
        delete_kudo,
        delete_team_event,
        delete_wiki_article,
        give_kudo,
        list_kudos,
        list_team_events,
        list_wiki_articles,
        update_wiki_article,
)
from src.service_layer.team_service import create_team
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer.user_service import register_user


@pytest.fixture
def uow():
        engine = create_engine("sqlite:///:memory:")
        metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        start_mappers()
        return SqlAlchemyUnitOfWork(session_factory)


def _setup_teams(uow, admin):
        create_team(uow, admin, "Time A")
        create_team(uow, admin, "Time B")
        team_a = uow.users.get_team_by_name("Time A").team_id
        team_b = uow.users.get_team_by_name("Time B").team_id
        return team_a, team_b


def _register_actor(uow, email, role, team_id):
        register_user(uow, email, "pass", role)
        user = uow.users.get_user_by_email(email)
        with uow:
                uow.users.set_user_team(user.user_id, team_id)
                uow.commit()
        return user.user_id


def _register_admin(uow):
        register_user(uow, "boss@test.com", "pass", UserRole.GESTOR.value)
        return uow.users.get_user_by_email("boss@test.com").user_id


# ---------------------------------------------------------------------------
# Wiki
# ---------------------------------------------------------------------------

def test_create_and_list_wiki_article(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        article = create_wiki_article(uow, admin, title="Guia", body="Como usar", team_id=team_a)
        assert article.wiki_article_id
        listed = list_wiki_articles(uow, admin)
        assert len(listed) == 1
        assert listed[0].title == "Guia"


def test_create_public_wiki_and_update(uow):
        admin = _register_admin(uow)
        _setup_teams(uow, admin)
        article = create_wiki_article(uow, admin, title="Público", body="Corpo")
        update_wiki_article(uow, admin, article.wiki_article_id, body="Novo corpo")
        listed = list_wiki_articles(uow, admin)
        assert listed[0].team_id is None
        assert listed[0].body == "Novo corpo"


def test_create_wiki_denied_out_of_scope(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        manager_a = _register_actor(uow, "mgr1@test.com", UserRole.MANAGER.value, team_a)
        with pytest.raises(PermissionError):
                create_wiki_article(uow, manager_a, title="X", body="Y", team_id=team_b)


def test_delete_wiki_author_or_manager(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        author = _register_actor(uow, "emp1@test.com", UserRole.EMPLOYEE.value, team_a)
        article = create_wiki_article(uow, author, title="A", body="B", team_id=team_a)
        delete_wiki_article(uow, author, article.wiki_article_id)
        assert list_wiki_articles(uow, admin) == []


# ---------------------------------------------------------------------------
# Kudos
# ---------------------------------------------------------------------------

def test_give_and_list_kudo(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        receiver = _register_actor(uow, "r1@test.com", UserRole.EMPLOYEE.value, team_a)
        giver = _register_actor(uow, "g1@test.com", UserRole.EMPLOYEE.value, team_a)
        kudo = give_kudo(uow, giver, team_id=team_a, receiver_id=receiver, message="Bom trabalho")
        assert kudo.kudo_id
        kudos = list_kudos(uow, admin)
        assert len(kudos) == 1
        assert kudos[0].message == "Bom trabalho"


def test_give_self_kudo_denied(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        user = _register_actor(uow, "s1@test.com", UserRole.EMPLOYEE.value, team_a)
        with pytest.raises(ValueError):
                give_kudo(uow, user, team_id=team_a, receiver_id=user, message="eu")


def test_delete_kudo_giver_only(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        receiver = _register_actor(uow, "d1@test.com", UserRole.EMPLOYEE.value, team_a)
        giver = _register_actor(uow, "d2@test.com", UserRole.EMPLOYEE.value, team_a)
        kudo = give_kudo(uow, giver, team_id=team_a, receiver_id=receiver, message="op")
        same_team_emp = _register_actor(uow, "d4@test.com", UserRole.EMPLOYEE.value, team_a)
        with pytest.raises(PermissionError):
                delete_kudo(uow, same_team_emp, kudo.kudo_id)
        delete_kudo(uow, giver, kudo.kudo_id)
        assert list_kudos(uow, admin) == []


# ---------------------------------------------------------------------------
# Team events
# ---------------------------------------------------------------------------

def test_create_and_list_event(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        create_team_event(uow, admin, team_id=team_a, title="Happy hour", date=date(2026, 1, 20), description="17h")
        events = list_team_events(uow, admin)
        assert len(events) == 1
        assert events[0].title == "Happy hour"


def test_create_event_requires_title_and_employee_denied(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        emp = _register_actor(uow, "e1@test.com", UserRole.EMPLOYEE.value, team_a)
        with pytest.raises(ValueError):
                create_team_event(uow, admin, team_id=team_a, title="", date=date(2026, 1, 1))
        with pytest.raises(PermissionError):
                create_team_event(uow, emp, team_id=team_a, title="X", date=date(2026, 1, 1))


def test_delete_event_manager_only(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        event = create_team_event(uow, admin, team_id=team_a, title="T", date=date(2026, 1, 1))
        emp = _register_actor(uow, "e2@test.com", UserRole.EMPLOYEE.value, team_a)
        with pytest.raises(PermissionError):
                delete_team_event(uow, emp, event.event_id)
        delete_team_event(uow, admin, event.event_id)
        assert list_team_events(uow, admin) == []