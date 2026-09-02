import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.domain.model import UserRole
from src.service_layer.idea_service import (
        create_idea,
        delete_idea,
        get_idea,
        list_ideas,
        set_idea_status,
        vote_idea,
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


def _create(uow, actor, team_id, title, category="idea"):
        with uow:
                idea = create_idea(uow, actor, team_id=team_id, title=title, category=category)
                return idea.idea_id


def _idea(uow, idea_id):
        with uow:
                return uow.users.get_idea_by_id(idea_id)


def test_create_idea_employee_posts_to_own_team(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        employee = _register_actor(uow, "empI@test.com", UserRole.EMPLOYEE.value, team_a)
        with uow:
                idea = create_idea(uow, employee, team_id=team_a, title="Melhorar onboarding", category="idea")
        assert idea.idea_id is not None
        assert _idea(uow, idea.idea_id).author_user_id == employee


def test_create_idea_requires_title(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        employee = _register_actor(uow, "empT@test.com", UserRole.EMPLOYEE.value, team_a)
        with pytest.raises(ValueError):
                create_idea(uow, employee, team_id=team_a, title="   ")


def test_create_idea_denied_out_of_scope_team(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        employee = _register_actor(uow, "empO@test.com", UserRole.EMPLOYEE.value, team_a)
        with pytest.raises(PermissionError):
                create_idea(uow, employee, team_id=team_b, title="Fora do escopo")


def test_list_ideas_scoped_by_team_and_category(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        _create(uow, admin, team_a, "Ideia A", category="idea")
        _create(uow, admin, team_a, "Kaizen A", category="kaizen")
        _create(uow, admin, team_b, "Ideia B", category="idea")
        employee_a = _register_actor(uow, "empL@test.com", UserRole.EMPLOYEE.value, team_a)
        all_titles = [i.title for i in list_ideas(uow, employee_a)]
        assert "Ideia A" in all_titles
        assert "Kaizen A" in all_titles
        assert "Ideia B" not in all_titles

        kaizen_titles = [i.title for i in list_ideas(uow, employee_a, category="kaizen")]
        assert "Kaizen A" in kaizen_titles
        assert "Ideia A" not in kaizen_titles


def test_vote_toggle_and_unique_per_voter(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        idea_id = _create(uow, admin, team_a, "Votável")
        voter = _register_actor(uow, "empV@test.com", UserRole.EMPLOYEE.value, team_a)

        assert vote_idea(uow, voter, idea_id) is True
        assert _idea(uow, idea_id).votes[0].voter_user_id == voter

        assert vote_idea(uow, voter, idea_id) is False
        assert _idea(uow, idea_id).votes == []


def test_vote_denied_out_of_scope(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        idea_id = _create(uow, admin, team_a, "Votar fora")
        outsider = _register_actor(uow, "empX@test.com", UserRole.EMPLOYEE.value, team_b)
        with pytest.raises(PermissionError):
                vote_idea(uow, outsider, idea_id)


def test_set_status_manager_only_including_implemented(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        idea_id = _create(uow, admin, team_a, "Implementável")
        manager_b = _register_actor(uow, "mgrB@test.com", UserRole.MANAGER.value, team_b)
        author = _register_actor(uow, "empS@test.com", UserRole.EMPLOYEE.value, team_a)

        with pytest.raises(PermissionError):
                set_idea_status(uow, manager_b, idea_id, "implemented")

        with pytest.raises(PermissionError):
                set_idea_status(uow, author, idea_id, "implemented")

        set_idea_status(uow, admin, idea_id, "under_review")
        assert _idea(uow, idea_id).status == "under_review"

        set_idea_status(uow, admin, idea_id, "implemented")
        assert _idea(uow, idea_id).status == "implemented"


def test_set_status_invalid_rejected(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        idea_id = _create(uow, admin, team_a, "Status inválido")
        with pytest.raises(ValueError):
                set_idea_status(uow, admin, idea_id, "nope")


def test_delete_idea_author_or_manager_only(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        author = _register_actor(uow, "empA@test.com", UserRole.EMPLOYEE.value, team_a)
        stranger = _register_actor(uow, "empR@test.com", UserRole.EMPLOYEE.value, team_a)
        idea_id = _create(uow, author, team_a, "Excluir")
        with pytest.raises(PermissionError):
                delete_idea(uow, stranger, idea_id)
        delete_idea(uow, author, idea_id)
        assert _idea(uow, idea_id) is None