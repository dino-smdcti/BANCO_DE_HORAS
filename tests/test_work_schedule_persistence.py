import unittest
from datetime import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.domain.model import User, UserRole, WorkSchedule
from src.service_layer.services import set_work_schedule
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.adapters.orm import start_mappers, metadata

class TestWorkSchedulePersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:")
        metadata.create_all(cls.engine)
        cls.session_factory = sessionmaker(bind=cls.engine)
        start_mappers()

    def setUp(self):
        self.session = SqlAlchemyUnitOfWork(self.session_factory)
        with self.session:
            # Create a test manager and employee
            manager = User(email="mgr@test.com", password_hash="!", role=UserRole.MANAGER)
            employee = User(email="emp@test.com", password_hash="!", role=UserRole.EMPLOYEE)
            self.session.session.add(manager)
            self.session.session.add(employee)
            self.session.commit()
            self.manager_id = manager.user_id
            self.employee_id = employee.user_id

    def test_set_work_schedule_persistence(self):
        new_arrival = time(9, 0)
        new_departure = time(18, 0)
        
        with self.session:
            set_work_schedule(
                self.session, self.manager_id, self.employee_id,
                new_arrival, None, None, new_departure, 15, False
            )
            
            # Fetch and verify
            emp = self.session.users.get_user_by_id(self.employee_id)
            self.assertIsNotNone(emp.work_schedule)
            self.assertEqual(emp.work_schedule.expected_arrival, new_arrival)
            self.assertEqual(emp.work_schedule.expected_departure, new_departure)

if __name__ == "__main__":
    unittest.main()
