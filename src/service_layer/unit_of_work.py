from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.adapters.repository import AbstractRepository, SqlAlchemyRepository
from src.adapters.orm import metadata
from src.domain.model import AuditLog

import os

database_url = os.environ.get("DATABASE_URL", "sqlite:///banco_de_horas.db")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

DEFAULT_SESSION_FACTORY = sessionmaker(
    bind=create_engine(database_url),
    expire_on_commit=False
)

class AbstractUnitOfWork(ABC):
    users: AbstractRepository
    session: Session

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.rollback()

    @abstractmethod
    def record_action(self, user_id: int, action: str, target_id: Optional[int] = None, details: Optional[str] = None):
        pass

    @abstractmethod
    def commit(self):
        pass

    @abstractmethod
    def rollback(self):
        pass

class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    def __init__(self, session_factory=DEFAULT_SESSION_FACTORY):
        self.session_factory = session_factory
        self._nested_count = 0

    def __enter__(self):
        if self._nested_count == 0:
            self.session: Session = self.session_factory()
            self.users = SqlAlchemyRepository(self.session)
        self._nested_count += 1
        return super().__enter__()

    def __exit__(self, *args):
        self._nested_count -= 1
        if self._nested_count == 0:
            super().__exit__(*args)
            self.session.close()
        else:
            # If nested, we don't call super().__exit__ because it rolls back by default
            # but we might want to check for errors. For now, just decrement.
            pass

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()

    def record_action(self, user_id: int, action: str, target_id: Optional[int] = None, details: Optional[str] = None):
        log = AuditLog(user_id=user_id, action=action, target_id=target_id, timestamp=datetime.now(), details=details)
        self.session.add(log)
