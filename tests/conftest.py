import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, clear_mappers
from src.adapters.orm import metadata, start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork

@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    return engine

@pytest.fixture
def session_factory(in_memory_db):
    start_mappers()
    yield sessionmaker(bind=in_memory_db)
    clear_mappers()

@pytest.fixture
def uow(session_factory):
    return SqlAlchemyUnitOfWork(session_factory)
