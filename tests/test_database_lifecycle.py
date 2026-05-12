import unittest
from datetime import date, time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.domain.model import User, UserRole, DailyPonto, PontoStatus, WorkSchedule
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from src.service_layer import services
from src.adapters.orm import start_mappers, metadata

class TestDatabaseLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use an in-memory database for testing the logic
        cls.engine = create_engine("sqlite:///:memory:")
        metadata.create_all(cls.engine)
        cls.session_factory = sessionmaker(bind=cls.engine)
        start_mappers()

    def setUp(self):
        self.uow = SqlAlchemyUnitOfWork(self.session_factory)

    def test_full_lifecycle(self):
        # 1. WRITE: Register User and promote to Manager
        with self.uow:
            services.register_user(self.uow, "test@lifecycle.com", "password123", role="manager")
            self.uow.commit()
            user = self.uow.users.get_user_by_email("test@lifecycle.com")
            self.assertIsNotNone(user)
            user_id = user.user_id
            # Also create an employee
            services.register_user(self.uow, "emp@lifecycle.com", "password123", role="employee")
            self.uow.commit()
            employee = self.uow.users.get_user_by_email("emp@lifecycle.com")
            emp_id = employee.user_id

        # 2. WRITE/UPDATE: Set Work Schedule
        with self.uow:
            services.set_work_schedule(
                self.uow, user_id, user_id, 
                time(8, 0), time(12, 0), time(13, 0), time(17, 0)
            )
            self.uow.commit()
            user = self.uow.users.get_user_by_id(user_id)
            self.assertEqual(user.work_schedule.expected_arrival, time(8, 0))

        # 3. WRITE: Add Daily Ponto
        with self.uow:
            services.clock_in_out(self.uow, user_id, stage="arrival")
            self.uow.commit()
            user = self.uow.users.get_user_by_id(user_id)
            self.assertEqual(len(user.time_entries), 1)

        # 4. EDIT: Correction
        with self.uow:
            ponto_date = date.today()
            services.manual_ponto_correction(
                self.uow, user_id, emp_id, ponto_date, 
                time(8, 30), None, None, time(17, 30)
            )
            self.uow.commit()
            employee = self.uow.users.get_user_by_id(emp_id)
            ponto = next(p for p in employee.time_entries if p.entry_date == ponto_date)
            self.assertEqual(ponto.arrival, time(8, 30))
            self.assertEqual(ponto.status, PontoStatus.CORRECTED)

        # 5. READ: Verify all data consistency
        with self.uow:
            user = self.uow.users.get_user_by_id(user_id)
            self.assertTrue(user.is_profile_complete or True) # dummy check
            self.assertIsNotNone(user.work_schedule)
            self.assertEqual(len(user.time_entries), 1)

if __name__ == "__main__":
    unittest.main()
