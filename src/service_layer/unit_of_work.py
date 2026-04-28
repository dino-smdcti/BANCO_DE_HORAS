from abc import ABC, abstractmethod
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.adapters.repository import AbstractRepository, SqlAlchemyRepository
from src.adapters.orm import metadata

DEFAULT_SESSION_FACTORY = sessionmaker(bind=create_engine("sqlite:///banco_de_horas.db"))

class AbstractUnitOfWork(ABC):
    users: AbstractRepository

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

    def __enter__(self):
        self.session: Session = self.session_factory()
        self.users = SqlAlchemyRepository(self.session)
        return super().__enter__()

    def __exit__(self, *args):
        super().__exit__(*args)
        self.session.close()

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()
