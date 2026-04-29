from abc import ABC, abstractmethod
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.adapters.repository import AbstractRepository, SqlAlchemyRepository
from src.adapters.orm import metadata

DEFAULT_SESSION_FACTORY = sessionmaker(
    bind=create_engine("sqlite:///banco_de_horas.db"),
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
