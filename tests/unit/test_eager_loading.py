from datetime import date, time

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.adapters.orm import metadata, start_mappers
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.domain.model import User, UserRole, WorkSchedule, DailyPonto, PontoStatus


def _query_counter(engine):
    state = {"n": 0}

    @event.listens_for(engine, "after_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):
        state["n"] += 1

    return state


def _build_employees(engine, n=3):
    start_mappers()
    factory = sessionmaker(bind=engine)
    uow = SqlAlchemyUnitOfWork(factory)
    with uow:
        for i in range(n):
            user = User(email=f"emp{i}@test.com", password_hash="!", role=UserRole.EMPLOYEE)
            user.work_schedule = WorkSchedule(
                user_id=user.user_id,
                expected_arrival=time(8, 0),
                expected_lunch_start=time(12, 0),
                expected_lunch_end=time(13, 0),
                expected_departure=time(17, 0),
                tolerance_minutes=5,
            )
            user.time_entries.append(DailyPonto(user_id=user.user_id, entry_date=date(2026, 5, 4), status=PontoStatus.ON_TIME))
            uow.session.add(user)
        uow.commit()
    return factory


class TestEagerLoading:
    def test_list_employees_does_not_n_plus_one(self, in_memory_db):
        factory = _build_employees(in_memory_db)
        counter = _query_counter(in_memory_db)
        uow = SqlAlchemyUnitOfWork(factory)
        with uow:
            employees = uow.users.list_employees()
            before = counter["n"]
            assert len(employees) == 3
            for employee in employees:
                _ = employee.time_entries
                _ = employee.vacations
                _ = employee.attestations
                _ = employee.work_schedule
                _ = employee.notifications
            after = counter["n"]
            assert after == before
