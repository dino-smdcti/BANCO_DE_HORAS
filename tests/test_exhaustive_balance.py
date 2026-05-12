import unittest
from datetime import date, time
from src.domain.model import User, WorkSchedule, DailyPonto, PontoStatus

class TestExhaustiveBalance(unittest.TestCase):
    def test_combinations(self):
        scenarios = [
            # (name, has_lunch, arrival, departure, worked_mins, expected_target, expected_balance)
            ("8h_with_lunch", True, time(8,0), time(17,0), 480, 480, 0),
            ("8h_no_lunch", False, time(8,0), time(16,0), 480, 480, 0),
            ("6h_with_lunch", True, time(8,0), time(14,0), 300, 300, 0),
            ("6h_no_lunch", False, time(8,0), time(14,0), 360, 360, 0),
            ("6h_no_lunch_early_departure", False, time(8,0), time(13,30), 330, 360, -30),
        ]

        for name, has_lunch, arrival, departure, worked, target, expected_bal in scenarios:
            # Setup
            lunch_start, lunch_end = (time(12,0), time(13,0)) if has_lunch else (None, None)
            sched = WorkSchedule(user_id=1, expected_arrival=arrival, 
                                 expected_lunch_start=lunch_start, expected_lunch_end=lunch_end, 
                                 expected_departure=departure, has_lunch_break=has_lunch)
            
            user = User(email=f"{name}@test.com", password_hash="!", role="employee", work_schedule=sched)
            
            # Create Ponto
            ponto = DailyPonto(user_id=1, entry_date=date(2026, 5, 2), status=PontoStatus.ON_TIME)
            ponto.arrival = arrival
            ponto.departure = departure
            ponto.lunch_start = lunch_start
            ponto.lunch_end = lunch_end
            ponto.has_lunch_break = has_lunch
            
            user.time_entries.append(ponto)
            
            # Logic check
            self.assertEqual(ponto.worked_minutes, worked, f"Failed worked_minutes for {name}")
            self.assertTrue(ponto.is_complete, f"Day not complete for {name}")
            self.assertEqual(user.total_balance, expected_bal, f"Failed balance for {name}")

if __name__ == "__main__":
    unittest.main()
