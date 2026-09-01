import os
import sys
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.adapters.repository import AbstractRepository, SqlAlchemyRepository
from src.domain.model import AuditLog
from src.config import LOCAL_SQLITE_URL, POSTGRES_SCHEME_POSTGRES, POSTGRES_SCHEME_POSTGRESQL, VERCEL_SQLITE_URL


def resolve_database_url(environ=None):
        """Resolve the active database URL with portability guards.

        Precedence: DATABASE_URL, POSTGRES_URL, Vercel /tmp SQLite (guarded,
        warning logged), then the local development SQLite file. The Vercel
        /tmp SQLite fallback is ephemeral (data is lost between cold starts),
        so it is only allowed with an explicit ALLOW_EPHEMERAL_SQLITE opt-in
        and it logs the durability caveat loudly to stderr.
        """
        environ = environ if environ is not None else os.environ
        database_url = environ.get("DATABASE_URL") or environ.get("POSTGRES_URL")
        if database_url:
                if database_url.startswith(POSTGRES_SCHEME_POSTGRES):
                        database_url = database_url.replace(POSTGRES_SCHEME_POSTGRES, POSTGRES_SCHEME_POSTGRESQL, 1)
                return database_url
        if environ.get("VERCEL"):
                if not environ.get("ALLOW_EPHEMERAL_SQLITE"):
                        raise RuntimeError("VERCEL detected without DATABASE_URL: configure a Postgres database, or set ALLOW_EPHEMERAL_SQLITE=1 to use the ephemeral /tmp SQLite fallback.")
                print("WARNING: Using ephemeral /tmp SQLite on Vercel; data is lost on cold start. Set DATABASE_URL for persistent storage.", file=sys.stderr)
                return VERCEL_SQLITE_URL
        return LOCAL_SQLITE_URL


def get_session_factory():
        database_url = resolve_database_url()
        return sessionmaker(
                bind=create_engine(database_url),
                expire_on_commit=False
        )

DEFAULT_SESSION_FACTORY = None


class AbstractUnitOfWork(ABC):
        users: AbstractRepository
        tokens: AbstractRepository
        rate_limit: AbstractRepository
        session: Session

        def __enter__(self):
                return self

        def __exit__(self, *args):
                raise NotImplementedError("Subclasses must implement __exit__")

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
        def __init__(self, session_factory=None):
                self.session_factory = session_factory or get_session_factory()
                self._nested_count = 0

        def __enter__(self):
                _start_session(self)
                self._nested_count += 1
                return super().__enter__()

        def __exit__(self, exc_type, exc_val, exc_tb):
                self._nested_count -= 1
                if self._nested_count == 0:
                        _close_session(self, exc_type)
                elif exc_type is not None:
                        self.rollback()

        def commit(self):
                self.session.commit()

        def rollback(self):
                self.session.rollback()

        def record_action(self, user_id: int, action: str, target_id: Optional[int] = None, details: Optional[str] = None):
                log = AuditLog(user_id=user_id, action=action, target_id=target_id, timestamp=datetime.now(), details=details)
                self.session.add(log)


def _start_session(uow):
        if uow._nested_count == 0:
                uow.session = uow.session_factory()
                uow.users = SqlAlchemyRepository(uow.session)
                uow.tokens = SqlAlchemyRepository(uow.session)
                uow.rate_limit = SqlAlchemyRepository(uow.session)


def _close_session(uow, exc_type):
        if exc_type is None:
                uow.commit()
        else:
                uow.rollback()
        uow.session.close()
