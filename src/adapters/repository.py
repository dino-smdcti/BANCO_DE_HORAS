from abc import ABC, abstractmethod
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from src.domain.model import User, UserRole, AuthToken

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
                return self.session.execute(select(User).where(User.role == UserRole.EMPLOYEE)).scalars().all()

        def list_all(self) -> List[User]:
                return self.session.execute(select(User)).scalars().all()

        def add_token(self, token: AuthToken):
                self.session.add(token)

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

