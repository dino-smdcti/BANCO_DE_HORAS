from datetime import date, time
from typing import List, Optional
from sqlalchemy import select

from src.domain.model import WorkSchedule, JourneyType, ScheduleType
from src.service_layer.unit_of_work import AbstractUnitOfWork
from src.service_layer.permissions import ensure_manager
from src.service_layer.audit import log_action


def set_work_schedule(uow: AbstractUnitOfWork, manager_id: int, employee_id: int, arrival: time, lunch_start: Optional[time], lunch_end: Optional[time], departure: time, tolerance: int = 15, has_lunch_break: bool = True, schedule_type: str = "standard", rotation_start_date: Optional[date] = None):
        with uow:
                _apply_schedule(uow, manager_id, employee_id, arrival, lunch_start, lunch_end, departure, tolerance, has_lunch_break, schedule_type, rotation_start_date)


def create_journey_type(uow: AbstractUnitOfWork, manager_id: int, name: str, arrival: time, lunch_start: Optional[time], lunch_end: Optional[time], departure: time, tolerance: int = 15, has_lunch_break: bool = True, schedule_type: str = "standard"):
        with uow:
                _create_journey(uow, manager_id, name, arrival, lunch_start, lunch_end, departure, tolerance, has_lunch_break, schedule_type)


def list_journey_types(uow: AbstractUnitOfWork) -> List[JourneyType]:
        with uow:
                return uow.session.execute(select(JourneyType)).scalars().all()


def get_journey_type(uow: AbstractUnitOfWork, journey_id: int) -> Optional[JourneyType]:
        with uow:
                return uow.session.execute(select(JourneyType).where(JourneyType.journey_id == journey_id)).scalar_one_or_none()


def update_journey_type(uow: AbstractUnitOfWork, manager_id: int, journey_id: int, name: str, arrival: time, lunch_start: Optional[time], lunch_end: Optional[time], departure: time, tolerance: int = 15, has_lunch_break: bool = True, schedule_type: str = "standard"):
        with uow:
                _apply_journey_update(uow, manager_id, journey_id, name, arrival, lunch_start, lunch_end, departure, tolerance, has_lunch_break, schedule_type)


def delete_journey_type(uow: AbstractUnitOfWork, manager_id: int, journey_id: int):
        with uow:
                _perform_journey_delete(uow, manager_id, journey_id)


def _apply_schedule(uow, manager_id, employee_id, arrival, lunch_start, lunch_end, departure, tolerance, has_lunch_break, schedule_type, rotation_start_date):
        user = _require_employee(uow, employee_id)
        _authorize_schedule_change(uow, manager_id, employee_id, user)
        schedule_type = ScheduleType(schedule_type.lower())
        if user.work_schedule:
                _overwrite_schedule(user.work_schedule, arrival, lunch_start, lunch_end, departure, tolerance, has_lunch_break, schedule_type, rotation_start_date)
        else:
                user.work_schedule = _new_schedule(employee_id, arrival, lunch_start, lunch_end, departure, tolerance, has_lunch_break, schedule_type, rotation_start_date)
        uow.commit()


def _require_employee(uow, employee_id):
        user = uow.users.get_user_by_id(employee_id)
        if not user:
                raise ValueError("Employee not found.")
        return user


def _authorize_schedule_change(uow, manager_id, employee_id, user):
        """Self-assignment is only allowed when the employee has no schedule yet."""
        if manager_id == employee_id:
                if user.work_schedule:
                        raise PermissionError("Self-reassignment not allowed. Contact a manager.")
                return
        ensure_manager(uow, manager_id)


def _overwrite_schedule(schedule, arrival, lunch_start, lunch_end, departure, tolerance, has_lunch_break, schedule_type, rotation_start_date):
        schedule.expected_arrival = arrival
        schedule.expected_lunch_start = lunch_start
        schedule.expected_lunch_end = lunch_end
        schedule.expected_departure = departure
        schedule.tolerance_minutes = tolerance
        schedule.has_lunch_break = has_lunch_break
        schedule.schedule_type = schedule_type
        schedule.rotation_start_date = rotation_start_date


def _new_schedule(employee_id, arrival, lunch_start, lunch_end, departure, tolerance, has_lunch_break, schedule_type, rotation_start_date):
        return WorkSchedule(
                user_id=employee_id,
                expected_arrival=arrival,
                expected_lunch_start=lunch_start,
                expected_lunch_end=lunch_end,
                expected_departure=departure,
                tolerance_minutes=tolerance,
                has_lunch_break=has_lunch_break,
                schedule_type=schedule_type,
                rotation_start_date=rotation_start_date,
        )


def _create_journey(uow, manager_id, name, arrival, lunch_start, lunch_end, departure, tolerance, has_lunch_break, schedule_type):
        ensure_manager(uow, manager_id)
        journey = JourneyType(
                name=name,
                expected_arrival=arrival,
                expected_lunch_start=lunch_start,
                expected_lunch_end=lunch_end,
                expected_departure=departure,
                tolerance_minutes=tolerance,
                has_lunch_break=has_lunch_break,
                schedule_type=ScheduleType(schedule_type),
        )
        uow.session.add(journey)
        log_action(uow, manager_id, "CREATE_JOURNEY_TYPE", target_id=None, details=f"Nome: {name}, Almoço: {has_lunch_break}, Tipo: {schedule_type}")


def _apply_journey_update(uow, manager_id, journey_id, name, arrival, lunch_start, lunch_end, departure, tolerance, has_lunch_break, schedule_type):
        ensure_manager(uow, manager_id)
        journey = uow.session.execute(select(JourneyType).where(JourneyType.journey_id == journey_id)).scalar_one_or_none()
        if not journey:
                raise ValueError("Journey Type not found.")
        journey.name = name
        journey.expected_arrival = arrival
        journey.expected_lunch_start = lunch_start
        journey.expected_lunch_end = lunch_end
        journey.expected_departure = departure
        journey.tolerance_minutes = tolerance
        journey.has_lunch_break = has_lunch_break
        journey.schedule_type = ScheduleType(schedule_type)
        log_action(uow, manager_id, "UPDATE_JOURNEY_TYPE", target_id=journey_id, details=f"Nome: {name}, Almoço: {has_lunch_break}, Tipo: {schedule_type}")


def _perform_journey_delete(uow, manager_id, journey_id):
        ensure_manager(uow, manager_id)
        journey = uow.session.execute(select(JourneyType).where(JourneyType.journey_id == journey_id)).scalar_one_or_none()
        if not journey:
                return
        name = journey.name
        uow.session.delete(journey)
        log_action(uow, manager_id, "DELETE_JOURNEY_TYPE", target_id=journey_id, details=f"Deletado: {name}")
