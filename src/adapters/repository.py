from abc import ABC, abstractmethod
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload
from src.domain.model import User, UserRole, AuthToken, Team

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

