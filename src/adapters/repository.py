from abc import ABC, abstractmethod
from typing import List, Optional
from sqlalchemy.orm import Session
from src.domain.model import User, DailyPonto, UserRole

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
    def add_time_entry(self, entry: DailyPonto):
        pass

class SqlAlchemyRepository(AbstractRepository):
    def __init__(self, session: Session):
        self.session = session

    def add_user(self, user: User):
        self.session.add(user)

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.session.query(User).filter_by(email=email).first()

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return self.session.query(User).filter(User.user_id == user_id).first()

    def list_employees(self) -> List[User]:
        return self.session.query(User).filter_by(role=UserRole.EMPLOYEE).all()

    def list_all(self) -> List[User]:
        return self.session.query(User).all()

    def add_time_entry(self, entry: DailyPonto):
        self.session.add(entry)

