from datetime import datetime

from src.domain.model import TeamTask, TaskChecklistItem
from src.service_layer.audit import log_action
from src.service_layer.notifications import add_notification
from src.service_layer.permissions import managed_team_ids, scoped_team_ids
from src.service_layer.unit_of_work import AbstractUnitOfWork
from src.config import TASK_STATUSES


def _validate_status(status: str):
        if status not in TASK_STATUSES:
                raise ValueError("Status de tarefa inválido.")


def _scoped_teams(uow: AbstractUnitOfWork, actor_id: int) -> set[int]:
        """Team ids the actor manages (write scope), empty when not a manager."""
        try:
                return set(managed_team_ids(uow, actor_id))
        except PermissionError:
                return set()


def _ensure_manager_scope(uow: AbstractUnitOfWork, actor_id: int, team_id) -> set[int]:
        """Return managed teams after raising for roles without management scope."""
        teams = set(managed_team_ids(uow, actor_id))
        if int(team_id) not in teams:
                raise PermissionError("Ação restrita ao seu time.")
        return teams


def _resolve_event(uow: AbstractUnitOfWork, actor_id: int, team_id: int, event_id):
        """Validate an optional linked event and return its id or None."""
        if not event_id:
                return None
        event = uow.users.get_team_event_by_id(int(event_id))
        if not event:
                raise ValueError("Evento vinculado não encontrado.")
        if event.team_id not in _ensure_manager_scope(uow, actor_id, team_id):
                raise PermissionError("Evento fora do escopo do time.")
        return int(event_id)


def _incomplete_items(task: TeamTask) -> int:
        """Number of not-done checklist items; 0 for a task with no checklist."""
        items = task.checklist_items or []
        return sum(0 if item.done else 1 for item in items)


def create_task(
        uow: AbstractUnitOfWork,
        actor_id: int,
        *,
        team_id: int,
        title: str,
        description: str = None,
        assignee_id: int = None,
        due_date=None,
        event_id: int = None,
) -> TeamTask:
        with uow:
                managed = _ensure_manager_scope(uow, actor_id, team_id)
                title = (title or "").strip()
                if not title:
                        raise ValueError("O título da tarefa é obrigatório.")
                if assignee_id:
                        scoped = set(scoped_team_ids(uow, actor_id))
                        assignee = uow.users.get_user_by_id(assignee_id)
                        if not assignee:
                                raise ValueError("Responsável não encontrado.")
                        if int(team_id) not in scoped and assignee.team_id != int(team_id):
                                raise PermissionError("Responsável fora do escopo do time.")
                event_id = _resolve_event(uow, actor_id, team_id, event_id)
                task = TeamTask(
                        team_id=int(team_id),
                        title=title,
                        description=(description or "").strip() or None,
                        assignee_id=int(assignee_id) if assignee_id else None,
                        due_date=due_date,
                        event_id=event_id,
                        created_by=actor_id,
                )
                uow.users.add_task(task)
                uow.commit()
                log_action(uow, actor_id, "CREATE_TASK", target_id=task.task_id, details=f"Task: {title}")
                if task.assignee_id:
                        add_notification(uow, task.assignee_id, f"Nova tarefa atribuída a você: {title}")
                return task


def list_tasks(uow: AbstractUnitOfWork, actor_id: int) -> list[TeamTask]:
        """Tasks visible to the actor (their team(s)) plus any assigned to them."""
        with uow:
                visible_team_ids = set(scoped_team_ids(uow, actor_id))
                tasks: list[TeamTask] = []
                for team_id in visible_team_ids:
                        tasks.extend(uow.users.list_tasks_by_team(team_id))
                if actor_id:
                        tasks.extend(uow.users.list_tasks_by_assignee(actor_id))
                return _dedupe_tasks(tasks)


def _dedupe_tasks(tasks: list[TeamTask]) -> list[TeamTask]:
        seen = set()
        unique = []
        for task in tasks:
                if task.task_id not in seen:
                        seen.add(task.task_id)
                        unique.append(task)
        return unique


def _get_managed_or_assigned_task(uow: AbstractUnitOfWork, actor_id: int, task_id: int) -> TeamTask:
        """Return a task if the actor manages it or is its assignee; else raise."""
        task = uow.users.get_task_by_id(task_id)
        if not task:
                raise ValueError("Tarefa não encontrada.")
        managed = _scoped_teams(uow, actor_id)
        if task.team_id in managed or task.assignee_id == actor_id:
                return task
        raise PermissionError("Ação restrita ao seu time ou às suas tarefas.")


def get_task(uow: AbstractUnitOfWork, actor_id: int, task_id: int) -> TeamTask:
        with uow:
                return _get_managed_or_assigned_task(uow, actor_id, task_id)


def update_task_status(uow: AbstractUnitOfWork, actor_id: int, task_id: int, status: str):
        with uow:
                _validate_status(status)
                task = _get_managed_or_assigned_task(uow, actor_id, task_id)
                if status == "done" and _incomplete_items(task):
                        raise ValueError("Conclua todos os itens do checklist antes de marcar a tarefa como concluída.")
                uow.users.update_task(task_id, status=status)
                uow.commit()
                log_action(uow, actor_id, "UPDATE_TASK_STATUS", target_id=task_id, details=f"Task {task_id} -> {status}")


def edit_task(
        uow: AbstractUnitOfWork,
        actor_id: int,
        task_id: int,
        *,
        title: str = None,
        description: str = None,
        assignee_id: int = None,
        due_date=None,
        event_id: int = None,
        clear_assignee: bool = False,
        clear_due_date: bool = False,
        clear_event: bool = False,
):
        with uow:
                task = uow.users.get_task_by_id(task_id)
                if not task:
                        raise ValueError("Tarefa não encontrada.")
                _ensure_manager_scope(uow, actor_id, task.team_id)
                resolved_title = (title or "").strip() if title is not None else None
                if resolved_title is not None and not resolved_title:
                        raise ValueError("O título da tarefa é obrigatório.")
                resolved_event = None if clear_event else event_id
                if resolved_event:
                        resolved_event = _resolve_event(uow, actor_id, task.team_id, resolved_event)
                uow.users.update_task(
                        task_id,
                        title=resolved_title,
                        description=(description.strip() or None) if description is not None else None,
                        assignee_id=int(assignee_id) if assignee_id else None,
                        due_date=due_date,
                        event_id=resolved_event,
                        clear_assignee=clear_assignee,
                        clear_due_date=clear_due_date,
                        clear_event=clear_event,
                )
                uow.commit()
                log_action(uow, actor_id, "UPDATE_TASK", target_id=task_id, details=f"Task {task_id} editada")
                new_assignee = None if clear_assignee else (int(assignee_id) if assignee_id else task.assignee_id)
                if new_assignee and new_assignee != task.assignee_id:
                        add_notification(uow, new_assignee, f"Nova tarefa atribuída a você: {resolved_title or task.title}")


def delete_task(uow: AbstractUnitOfWork, actor_id: int, task_id: int):
        with uow:
                task = uow.users.get_task_by_id(task_id)
                if not task:
                        raise ValueError("Tarefa não encontrada.")
                _ensure_manager_scope(uow, actor_id, task.team_id)
                uow.users.delete_task(task_id)
                uow.commit()
                log_action(uow, actor_id, "DELETE_TASK", target_id=task_id, details=f"Task {task.title}")


def add_checklist_item(uow: AbstractUnitOfWork, actor_id: int, task_id: int, label: str) -> TaskChecklistItem:
        with uow:
                label = (label or "").strip()
                if not label:
                        raise ValueError("O item do checklist é obrigatório.")
                task = _get_managed_or_assigned_task(uow, actor_id, task_id)
                item = TaskChecklistItem(task_id=task_id, label=label)
                uow.users.add_checklist_item(item)
                if task.status == "done":
                        uow.users.update_task(task_id, status="in_progress")
                uow.commit()
                log_action(uow, actor_id, "ADD_TASK_ITEM", target_id=task_id, details=f"Item: {label}")
                return item


def toggle_checklist_item(uow: AbstractUnitOfWork, actor_id: int, task_id: int, item_id: int, done: bool):
        with uow:
                task = _get_managed_or_assigned_task(uow, actor_id, task_id)
                uow.users.set_checklist_item_done(item_id, done)
                incomplete = _incomplete_items(task)
                if not incomplete and task.status != "done":
                        uow.users.update_task(task_id, status="done")
                elif incomplete and task.status == "done":
                        uow.users.update_task(task_id, status="in_progress")
                uow.commit()
                log_action(uow, actor_id, "TOGGLE_TASK_ITEM", target_id=task_id, details=f"Item {item_id} done={done}")


def remove_checklist_item(uow: AbstractUnitOfWork, actor_id: int, task_id: int, item_id: int):
        with uow:
                task = _get_managed_or_assigned_task(uow, actor_id, task_id)
                item = next((i for i in (task.checklist_items or []) if i.checklist_item_id == item_id), None)
                uow.users.delete_checklist_item(item_id)
                if (item and not item.done) and task.status == "done":
                        uow.users.update_task(task_id, status="in_progress")
                uow.commit()
                log_action(uow, actor_id, "DELETE_TASK_ITEM", target_id=task_id, details=f"Item {item_id}")