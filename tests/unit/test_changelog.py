import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.domain.model import UserRole
from src.service_layer.changelog_service import create_changelog_note, delete_changelog_note, list_changelog_notes
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


def _register_actor(uow, email, role):
        register_user(uow, email, "pass", role)
        return uow.users.get_user_by_email(email).user_id


def _setup(uow):
        admin = _register_actor(uow, "boss@test.com", UserRole.GESTOR.value)
        create_team(uow, admin, "Time")
        return admin


def test_manager_publishes_note(uow):
        _setup(uow)
        manager = _register_actor(uow, "mgr@test.com", UserRole.MANAGER.value)
        note = create_changelog_note(uow, manager, version_or_date="v2.4", title="Novo recurso", description="Detalhes", category="feature")
        assert note.changelog_id
        notes = list_changelog_notes(uow, manager)
        assert len(notes) == 1
        assert notes[0].title == "Novo recurso"
        assert notes[0].category == "feature"


def test_employee_cannot_publish(uow):
        _setup(uow)
        emp = _register_actor(uow, "emp@test.com", UserRole.EMPLOYEE.value)
        with pytest.raises(PermissionError):
                create_changelog_note(uow, emp, version_or_date="v2.4", title="X")


def test_requires_version_and_title(uow):
        admin = _setup(uow)
        with pytest.raises(ValueError):
                create_changelog_note(uow, admin, version_or_date="", title="")
        with pytest.raises(ValueError):
                create_changelog_note(uow, admin, version_or_date="v2.4", title="")


def test_invalid_category_defaults_to_feature(uow):
        admin = _setup(uow)
        note = create_changelog_note(uow, admin, version_or_date="v1", title="Z", category="banana")
        assert note.category == "feature"


def test_delete_note_manager_only(uow):
        admin = _setup(uow)
        emp = _register_actor(uow, "emp@test.com", UserRole.EMPLOYEE.value)
        note = create_changelog_note(uow, admin, version_or_date="v1", title="A")
        with pytest.raises(PermissionError):
                delete_changelog_note(uow, emp, note.changelog_id)
        delete_changelog_note(uow, admin, note.changelog_id)
        assert list_changelog_notes(uow, admin) == []


def test_publishing_notifies_all_users(uow):
        admin = _setup(uow)
        _register_actor(uow, "emp@test.com", UserRole.EMPLOYEE.value)
        create_changelog_note(uow, admin, version_or_date="v1", title="Patch")
        with uow:
                emp = uow.users.get_user_by_email("emp@test.com")
                assert any("Patch" in n.message for n in emp.notifications)