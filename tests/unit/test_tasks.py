import pytest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.domain.model import UserRole
from src.service_layer.task_service import (
        add_checklist_item,
        create_task,
        delete_task,
        edit_task,
        list_tasks,
        remove_checklist_item,
        toggle_checklist_item,
        update_task_status,
)
from src.service_layer.culture_service import create_team_event
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


def _create(uow, admin, team_id, title, assignee_id=None):
        with uow:
                task = create_task(uow, admin, team_id=team_id, title=title, assignee_id=assignee_id)
                return task.task_id


def _task(uow, task_id):
        with uow:
                return uow.users.get_task_by_id(task_id)


def test_create_task_assigns_and_notifies(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        assignee = _register_actor(uow, "emp@test.com", UserRole.EMPLOYEE.value, team_a)

        with uow:
                task = create_task(uow, admin, team_id=team_a, title="Montar relatório", assignee_id=assignee)
                task_id = task.task_id
                notif = uow.users.get_user_by_id(assignee).notifications

        assert task_id is not None
        assert any("Montar relatório" in n.message for n in notif)


def test_create_task_requires_title(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        with pytest.raises(ValueError):
                create_task(uow, admin, team_id=team_a, title="   ")


def test_create_task_denied_out_of_scope_team(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        manager = _register_actor(uow, "mgr@test.com", UserRole.MANAGER.value, team_a)
        with pytest.raises(PermissionError):
                create_task(uow, manager, team_id=team_b, title="Fora do escopo")


def test_create_task_denied_for_employee(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        employee = _register_actor(uow, "emp2@test.com", UserRole.EMPLOYEE.value, team_a)
        with pytest.raises(PermissionError):
                create_task(uow, employee, team_id=team_a, title="Sem permissão")


def test_list_tasks_manager_scoped_to_own_team(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        _create(uow, admin, team_a, "Tarefa time A")
        _create(uow, admin, team_b, "Tarefa time B")
        manager_a = _register_actor(uow, "mgrA@test.com", UserRole.MANAGER.value, team_a)
        titles = [t.title for t in list_tasks(uow, manager_a)]
        assert "Tarefa time A" in titles
        assert "Tarefa time B" not in titles


def test_list_tasks_employee_sees_own_team_and_assigned(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        employee = _register_actor(uow, "empA@test.com", UserRole.EMPLOYEE.value, team_a)
        _create(uow, admin, team_a, "Do meu time", assignee_id=employee)
        _create(uow, admin, team_b, "De outro time", assignee_id=employee)
        titles = [t.title for t in list_tasks(uow, employee)]
        assert "Do meu time" in titles
        assert "De outro time" in titles


def test_update_status_manager_and_assignee_allowed(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        assignee = _register_actor(uow, "empS@test.com", UserRole.EMPLOYEE.value, team_a)
        task_id = _create(uow, admin, team_a, "Status", assignee_id=assignee)

        # Assignee moves across working stages and submits for approval.
        update_task_status(uow, assignee, task_id, "in_execution")
        assert _task(uow, task_id).status == "in_execution"
        update_task_status(uow, assignee, task_id, "pending_approval")
        assert _task(uow, task_id).status == "pending_approval"

        # Only a manager approves (conclude).
        update_task_status(uow, admin, task_id, "done")
        assert _task(uow, task_id).status == "done"

        task2 = _create(uow, admin, team_a, "Status2", assignee_id=assignee)
        with pytest.raises(PermissionError):
                update_task_status(uow, assignee, task2, "done")


def test_status_invalid_rejected(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        task_id = _create(uow, admin, team_a, "Status inválido")
        with pytest.raises(ValueError):
                update_task_status(uow, admin, task_id, "nope")


def test_edit_task_manager_only(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        assignee = _register_actor(uow, "empE@test.com", UserRole.EMPLOYEE.value, team_a)
        task_id = _create(uow, admin, team_a, "Original")
        edit_task(uow, admin, task_id, title="Editada")
        assert _task(uow, task_id).title == "Editada"

        with pytest.raises(PermissionError):
                edit_task(uow, assignee, task_id, title="Sem permissão")


def test_delete_task_manager_only(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        assignee = _register_actor(uow, "empD@test.com", UserRole.EMPLOYEE.value, team_a)
        task_id = _create(uow, admin, team_a, "Excluir")
        with pytest.raises(PermissionError):
                delete_task(uow, assignee, task_id)
        delete_task(uow, admin, task_id)
        assert _task(uow, task_id) is None


def test_checklist_add_toggle_remove(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        assignee = _register_actor(uow, "empC@test.com", UserRole.EMPLOYEE.value, team_a)
        task_id = _create(uow, admin, team_a, "Checklist", assignee_id=assignee)

        with uow:
                item = add_checklist_item(uow, assignee, task_id, "Revisar texto")
                item_id = item.checklist_item_id
        assert item_id is not None

        toggle_checklist_item(uow, assignee, task_id, item_id, True)
        assert _task(uow, task_id).checklist_items[0].done is True

        remove_checklist_item(uow, admin, task_id, item_id)
        assert _task(uow, task_id).checklist_items == []


def test_create_task_linked_to_event(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        with uow:
                event = create_team_event(uow, admin, team_id=team_a, title="Treinamento", date=date(2026, 3, 1))
                event_id = event.event_id
        task_id = _create_event_task(uow, admin, team_a, "Preparar sala", event_id)
        assert _task(uow, task_id).event_id == event_id


def test_create_task_linked_event_out_of_scope_denied(uow):
        admin = _register_admin(uow)
        team_a, team_b = _setup_teams(uow, admin)
        manager = _register_actor(uow, "mgrEvt@test.com", UserRole.MANAGER.value, team_a)
        with uow:
                event = create_team_event(uow, admin, team_id=team_b, title="Outro time", date=date(2026, 3, 1))
                event_id = event.event_id
        with pytest.raises(PermissionError):
                create_task(uow, manager, team_id=team_a, title="X", event_id=event_id)


def test_done_requires_all_checklist_items(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        assignee = _register_actor(uow, "empG@test.com", UserRole.EMPLOYEE.value, team_a)
        task_id = _create(uow, admin, team_a, "Objetivo", assignee_id=assignee)
        with uow:
                i1 = add_checklist_item(uow, assignee, task_id, "Passo 1").checklist_item_id
                i2 = add_checklist_item(uow, assignee, task_id, "Passo 2").checklist_item_id

        with pytest.raises(ValueError):
                update_task_status(uow, admin, task_id, "done")

        toggle_checklist_item(uow, assignee, task_id, i1, True)
        with pytest.raises(ValueError):
                update_task_status(uow, admin, task_id, "done")


def test_task_auto_submits_for_approval_when_all_items_done(uow):
        admin = _register_admin(uow)
        team_a, _ = _setup_teams(uow, admin)
        assignee = _register_actor(uow, "empAuto@test.com", UserRole.EMPLOYEE.value, team_a)
        task_id = _create(uow, admin, team_a, "Atingir objetivo", assignee_id=assignee)
        with uow:
                i1 = add_checklist_item(uow, assignee, task_id, "A").checklist_item_id
                i2 = add_checklist_item(uow, assignee, task_id, "B").checklist_item_id

        toggle_checklist_item(uow, assignee, task_id, i1, True)
        assert _task(uow, task_id).status != "pending_approval"
        toggle_checklist_item(uow, assignee, task_id, i2, True)
        assert _task(uow, task_id).status == "pending_approval"

        toggle_checklist_item(uow, assignee, task_id, i1, False)
        assert _task(uow, task_id).status == "in_execution"


def _create_event_task(uow, admin, team_id, title, event_id):
        with uow:
                task = create_task(uow, admin, team_id=team_id, title=title, event_id=event_id)
                return task.task_id
