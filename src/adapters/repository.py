from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime, date
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import Session, selectinload
from src.domain.model import User, UserRole, AuthToken, Team, RateLimitEntry, TeamTask, TaskChecklistItem, Accomplishment, Idea, IdeaVote

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
        def update_team(
                self,
                team_id: int,
                *,
                name: Optional[str] = None,
                secretariat: Optional[str] = None,
                lead_user_id=None,
                clear_lead: bool = False,
        ):
                pass

        @abstractmethod
        def count_team_members(self, team_id: int) -> int:
                pass

        @abstractmethod
        def count_open_tasks_by_team(self, team_id: int) -> int:
                pass

        @abstractmethod
        def count_open_ideas_by_team(self, team_id: int) -> int:
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

        @abstractmethod
        def add_accomplishment(self, accomplishment: Accomplishment):
                pass

        @abstractmethod
        def get_accomplishment_by_id(self, accomplishment_id: int) -> Optional[Accomplishment]:
                pass

        @abstractmethod
        def list_accomplishments_by_team(self, team_id: int) -> List[Accomplishment]:
                pass

        @abstractmethod
        def update_accomplishment(
                self,
                accomplishment_id: int,
                *,
                title: Optional[str] = None,
                description: Optional[str] = None,
                start_date=None,
                end_date=None,
                achieved_by_user_id: Optional[int] = None,
                clear_end_date: bool = False,
        ):
                pass

        @abstractmethod
        def delete_accomplishment(self, accomplishment_id: int):
                pass

        @abstractmethod
        def add_idea(self, idea: Idea):
                pass

        @abstractmethod
        def get_idea_by_id(self, idea_id: int) -> Optional[Idea]:
                pass

        @abstractmethod
        def list_ideas_by_team(self, team_id: int) -> List[Idea]:
                pass

        @abstractmethod
        def update_idea(
                self,
                idea_id: int,
                *,
                status: Optional[str] = None,
                review_date=None,
                review_owner: Optional[str] = None,
                clear_review: bool = False,
        ):
                pass

        @abstractmethod
        def delete_idea(self, idea_id: int):
                pass

        @abstractmethod
        def add_idea_vote(self, vote: IdeaVote) -> Optional[IdeaVote]:
                pass

        @abstractmethod
        def get_idea_vote(self, idea_id: int, voter_user_id: int) -> Optional[IdeaVote]:
                pass

        @abstractmethod
        def delete_idea_vote(self, vote_id: int):
                pass

        @abstractmethod
        def count_idea_votes(self, idea_id: int) -> int:
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

        def update_team(
                self,
                team_id: int,
                *,
                name: Optional[str] = None,
                secretariat: Optional[str] = None,
                lead_user_id=None,
                clear_lead: bool = False,
        ):
                values = {}
                if name is not None:
                        values["name"] = name
                if secretariat is not None:
                        values["secretariat"] = secretariat
                if clear_lead:
                        values["lead_user_id"] = None
                elif lead_user_id is not None:
                        values["lead_user_id"] = int(lead_user_id)
                if values:
                        self.session.execute(
                                update(Team).where(Team.team_id == team_id).values(**values)
                        )

        def count_team_members(self, team_id: int) -> int:
                return self.session.execute(
                        select(func.count()).select_from(User).where(User.team_id == team_id)
                ).scalar_one()

        def count_open_tasks_by_team(self, team_id: int) -> int:
                from src.config import TASK_STATUS_DONE, TASK_STATUS_CANCELLED
                return self.session.execute(
                        select(func.count()).select_from(TeamTask).where(
                                TeamTask.team_id == team_id,
                                TeamTask.status.notin_([TASK_STATUS_DONE, TASK_STATUS_CANCELLED]),
                        )
                ).scalar_one()

        def count_open_ideas_by_team(self, team_id: int) -> int:
                from src.config import IDEA_STATUS_IMPLEMENTED, IDEA_STATUS_DECLINED
                return self.session.execute(
                        select(func.count()).select_from(Idea).where(
                                Idea.team_id == team_id,
                                Idea.status.notin_([IDEA_STATUS_IMPLEMENTED, IDEA_STATUS_DECLINED]),
                        )
                ).scalar_one()

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

        def add_accomplishment(self, accomplishment: Accomplishment):
                self.session.add(accomplishment)

        def get_accomplishment_by_id(self, accomplishment_id: int) -> Optional[Accomplishment]:
                return self.session.execute(
                        select(Accomplishment).where(Accomplishment.accomplishment_id == accomplishment_id)
                ).scalar_one_or_none()

        def list_accomplishments_by_team(self, team_id: int) -> List[Accomplishment]:
                return self.session.execute(
                        select(Accomplishment)
                        .where(Accomplishment.team_id == team_id)
                        .order_by(Accomplishment.start_date.desc())
                ).scalars().all()

        def update_accomplishment(
                self,
                accomplishment_id: int,
                *,
                title: Optional[str] = None,
                description: Optional[str] = None,
                start_date=None,
                end_date=None,
                achieved_by_user_id: Optional[int] = None,
                clear_end_date: bool = False,
        ):
                values = {}
                if title is not None:
                        values["title"] = title
                if description is not None:
                        values["description"] = description
                if start_date is not None:
                        values["start_date"] = start_date
                if clear_end_date:
                        values["end_date"] = None
                elif end_date is not None:
                        values["end_date"] = end_date
                if achieved_by_user_id is not None:
                        values["achieved_by_user_id"] = achieved_by_user_id
                if values:
                        self.session.execute(
                                update(Accomplishment).where(Accomplishment.accomplishment_id == accomplishment_id).values(**values)
                        )

        def delete_accomplishment(self, accomplishment_id: int):
                self.session.execute(
                        delete(Accomplishment).where(Accomplishment.accomplishment_id == accomplishment_id)
                )

        def add_idea(self, idea: Idea):
                self.session.add(idea)

        def get_idea_by_id(self, idea_id: int) -> Optional[Idea]:
                return self.session.execute(
                        select(Idea)
                        .where(Idea.idea_id == idea_id)
                        .options(selectinload(Idea.votes))
                ).scalar_one_or_none()

        def list_ideas_by_team(self, team_id: int) -> List[Idea]:
                return self.session.execute(
                        select(Idea)
                        .where(Idea.team_id == team_id)
                        .options(selectinload(Idea.votes))
                        .order_by(Idea.created_at.desc())
                ).scalars().all()

        def update_idea(
                self,
                idea_id: int,
                *,
                status: Optional[str] = None,
                review_date=None,
                review_owner: Optional[str] = None,
                clear_review: bool = False,
        ):
                values = {}
                if status is not None:
                        values["status"] = status
                if clear_review:
                        values["review_date"] = None
                        values["review_owner"] = None
                else:
                        if review_date is not None:
                                values["review_date"] = review_date
                        if review_owner is not None:
                                values["review_owner"] = review_owner
                if values:
                        self.session.execute(
                                update(Idea).where(Idea.idea_id == idea_id).values(**values)
                        )

        def delete_idea(self, idea_id: int):
                self.session.execute(
                        delete(Idea).where(Idea.idea_id == idea_id)
                )

        def add_idea_vote(self, vote: IdeaVote) -> Optional[IdeaVote]:
                self.session.add(vote)
                return vote

        def get_idea_vote(self, idea_id: int, voter_user_id: int) -> Optional[IdeaVote]:
                return self.session.execute(
                        select(IdeaVote).where(
                                IdeaVote.idea_id == idea_id,
                                IdeaVote.voter_user_id == voter_user_id,
                        )
                ).scalar_one_or_none()

        def delete_idea_vote(self, vote_id: int):
                self.session.execute(
                        delete(IdeaVote).where(IdeaVote.vote_id == vote_id)
                )

        def count_idea_votes(self, idea_id: int) -> int:
                return self.session.execute(
                        select(func.count())
                        .select_from(IdeaVote)
                        .where(IdeaVote.idea_id == idea_id)
                ).scalar_one()

