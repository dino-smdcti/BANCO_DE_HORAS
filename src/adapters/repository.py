from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import Session, selectinload
from src.domain.model import User, UserRole, AuthToken, Team, RateLimitEntry, TeamTask, TaskChecklistItem

class AbstractRepository(ABC):
        @abstractmethod
        def add_user(self, user: User):
                pass

        @abstractmethod
        def get_user_by_email(self, email: str) -> Optional[User]:
                pass

        @abstractmethod
        def get_user_by_id(self, user_id: int) -> Optional[User]:
                pass

        @abstractmethod
        def list_employees(self) -> List[User]:
                pass

        @abstractmethod
        def list_all(self) -> List[User]:
                pass

        @abstractmethod
        def add_token(self, token: AuthToken):
                pass

        @abstractmethod
        def get_token_by_hash(self, token_hash: str, kind: str) -> Optional[AuthToken]:
                pass

        @abstractmethod
        def revoke_user_tokens(self, user_id: int, kind: str):
                pass

        @abstractmethod
        def add_rate_limit_entry(self, entry: RateLimitEntry):
                pass

        @abstractmethod
        def count_rate_limit_entries(self, bucket: str, since: datetime) -> int:
                pass

        @abstractmethod
        def prune_rate_limit_entries(self, before: datetime, limit: int) -> int:
                pass

        @abstractmethod
        def add_team(self, team: Team):
                pass

        @abstractmethod
        def get_team_by_id(self, team_id: int) -> Optional[Team]:
                pass

        @abstractmethod
        def get_team_by_name(self, name: str) -> Optional[Team]:
                pass

        @abstractmethod
        def list_teams(self) -> List[Team]:
                pass

        @abstractmethod
        def list_users_by_team(self, team_id: int) -> List[User]:
                pass

        @abstractmethod
        def list_user_ids_by_team(self, team_id: int) -> List[int]:
                pass

        @abstractmethod
        def set_user_team(self, user_id: int, team_id: Optional[int]):
                pass

        @abstractmethod
        def add_task(self, task: TeamTask):
                pass

        @abstractmethod
        def get_task_by_id(self, task_id: int) -> Optional[TeamTask]:
                pass

        @abstractmethod
        def list_tasks_by_team(self, team_id: int) -> List[TeamTask]:
                pass

        @abstractmethod
        def list_tasks_by_assignee(self, assignee_id: int) -> List[TeamTask]:
                pass

        @abstractmethod
        def update_task(
                self,
                task_id: int,
                *,
                title: Optional[str] = None,
                description: Optional[str] = None,
                assignee_id: Optional[int] = None,
                due_date=None,
                clear_assignee: bool = False,
                clear_due_date: bool = False,
                status: Optional[str] = None,
        ):
                pass

        @abstractmethod
        def delete_task(self, task_id: int):
                pass

        @abstractmethod
        def add_checklist_item(self, item: TaskChecklistItem):
                pass

        @abstractmethod
        def set_checklist_item_done(self, item_id: int, done: bool):
                pass

        @abstractmethod
        def delete_checklist_item(self, item_id: int):
                pass

class SqlAlchemyRepository(AbstractRepository):
        def __init__(self, session: Session):
                self.session = session

        def add_user(self, user: User):
                self.session.add(user)

        def get_user_by_email(self, email: str) -> Optional[User]:
                return self.session.execute(select(User).where(User.email == email)).scalar_one_or_none()

        def get_user_by_id(self, user_id: int) -> Optional[User]:
                return self.session.execute(select(User).where(User.user_id == user_id)).scalar_one_or_none()

        def list_employees(self) -> List[User]:
                return self.session.execute(
                        select(User)
                        .where(User.role == UserRole.EMPLOYEE)
                        .options(
                                selectinload(User.time_entries),
                                selectinload(User.vacations),
                                selectinload(User.attestations),
                                selectinload(User.work_schedule),
                                selectinload(User.notifications),
                        )
                ).scalars().all()

        def list_all(self) -> List[User]:
                return self.session.execute(
                        select(User)
                        .options(
                                selectinload(User.time_entries),
                                selectinload(User.vacations),
                                selectinload(User.attestations),
                                selectinload(User.work_schedule),
                                selectinload(User.notifications),
                        )
                ).scalars().all()

        def list_users_by_team(self, team_id: int) -> List[User]:
                return self.session.execute(
                        select(User)
                        .where(User.team_id == team_id)
                        .options(
                                selectinload(User.time_entries),
                                selectinload(User.vacations),
                                selectinload(User.attestations),
                                selectinload(User.work_schedule),
                                selectinload(User.notifications),
                        )
                ).scalars().all()

        def list_user_ids_by_team(self, team_id: int) -> List[int]:
                return self.session.execute(select(User.user_id).where(User.team_id == team_id)).scalars().all()

        def add_token(self, token: AuthToken):
                self.session.add(token)

        def add_team(self, team: Team):
                self.session.add(team)

        def get_team_by_id(self, team_id: int) -> Optional[Team]:
                return self.session.execute(select(Team).where(Team.team_id == team_id)).scalar_one_or_none()

        def get_team_by_name(self, name: str) -> Optional[Team]:
                return self.session.execute(select(Team).where(Team.name == name)).scalar_one_or_none()

        def list_teams(self) -> List[Team]:
                return self.session.execute(select(Team).order_by(Team.name)).scalars().all()

        def set_user_team(self, user_id: int, team_id: Optional[int]):
                self.session.execute(
                        update(User).where(User.user_id == user_id).values(team_id=team_id)
                )

        def get_token_by_hash(self, token_hash: str, kind: str) -> Optional[AuthToken]:
                return self.session.execute(
                        select(AuthToken).where(AuthToken.token_hash == token_hash, AuthToken.kind == kind)
                ).scalar_one_or_none()

        def revoke_user_tokens(self, user_id: int, kind: str):
                self.session.execute(
                        update(AuthToken)
                        .where(AuthToken.user_id == user_id, AuthToken.kind == kind, AuthToken.used == False)
                        .values(used=True)
                )

        def add_rate_limit_entry(self, entry: RateLimitEntry):
                self.session.add(entry)

        def count_rate_limit_entries(self, bucket: str, since: datetime) -> int:
                return self.session.execute(
                        select(func.count(RateLimitEntry.entry_id)).where(
                                RateLimitEntry.bucket == bucket,
                                RateLimitEntry.created_at >= since,
                        )
                ).scalar_one()

        def prune_rate_limit_entries(self, before: datetime, limit: int) -> int:
                expired_ids = self.session.execute(
                        select(RateLimitEntry.entry_id)
                        .where(RateLimitEntry.created_at < before)
                        .limit(limit)
                ).scalars().all()
                if not expired_ids:
                        return 0
                result = self.session.execute(
                        delete(RateLimitEntry).where(RateLimitEntry.entry_id.in_(expired_ids))
                )
                return result.rowcount or 0

        def add_task(self, task: TeamTask):
                self.session.add(task)

        def get_task_by_id(self, task_id: int) -> Optional[TeamTask]:
                return self.session.execute(
                        select(TeamTask)
                        .where(TeamTask.task_id == task_id)
                        .options(selectinload(TeamTask.checklist_items))
                ).scalar_one_or_none()

        def list_tasks_by_team(self, team_id: int) -> List[TeamTask]:
                return self.session.execute(
                        select(TeamTask)
                        .where(TeamTask.team_id == team_id)
                        .options(selectinload(TeamTask.checklist_items))
                        .order_by(TeamTask.created_at.desc())
                ).scalars().all()

        def list_tasks_by_assignee(self, assignee_id: int) -> List[TeamTask]:
                return self.session.execute(
                        select(TeamTask)
                        .where(TeamTask.assignee_id == assignee_id)
                        .options(selectinload(TeamTask.checklist_items))
                        .order_by(TeamTask.created_at.desc())
                ).scalars().all()

        def update_task(
                self,
                task_id: int,
                *,
                title: Optional[str] = None,
                description: Optional[str] = None,
                assignee_id: Optional[int] = None,
                due_date=None,
                clear_assignee: bool = False,
                clear_due_date: bool = False,
                status: Optional[str] = None,
        ):
                values = {}
                if title is not None:
                        values["title"] = title
                if description is not None:
                        values["description"] = description
                if clear_assignee:
                        values["assignee_id"] = None
                elif assignee_id is not None:
                        values["assignee_id"] = assignee_id
                if clear_due_date:
                        values["due_date"] = None
                elif due_date is not None:
                        values["due_date"] = due_date
                if status is not None:
                        values["status"] = status
                if values:
                        self.session.execute(
                                update(TeamTask).where(TeamTask.task_id == task_id).values(**values)
                        )

        def delete_task(self, task_id: int):
                self.session.execute(
                        delete(TeamTask).where(TeamTask.task_id == task_id)
                )

        def add_checklist_item(self, item: TaskChecklistItem):
                self.session.add(item)

        def set_checklist_item_done(self, item_id: int, done: bool):
                self.session.execute(
                        update(TaskChecklistItem).where(TaskChecklistItem.checklist_item_id == item_id).values(done=done)
                )

        def delete_checklist_item(self, item_id: int):
                self.session.execute(
                        delete(TaskChecklistItem).where(TaskChecklistItem.checklist_item_id == item_id)
                )

