import unittest
from datetime import date, time
from src.domain.model import User, WorkSchedule, DailyPonto, PontoStatus

class TestExhaustiveBalance(unittest.TestCase):
    def test_combinations(self):
        scenarios = [
            # name, has_lunch, arrival, departure, worked, target, expected_bal
            # Normal day
            ("8h_normal", True, time(8,0), time(17,0), 480, 480, 0),
            # Late arrival, same departure (-30m)
            ("8h_late_arrival", True, time(8,30), time(17,0), 450, 480, -30),
            # Early arrival, same departure (+30m)
            ("8h_early_arrival", True, time(7,30), time(17,0), 510, 480, 30),
            # Normal arrival, early departure (-30m)
            ("8h_early_departure", True, time(8,0), time(16,30), 450, 480, -30),
            # Normal arrival, late departure (+30m)
            ("8h_late_departure", True, time(8,0), time(17,30), 510, 480, 30),
            # 6h scenario: Early arrival, early departure (still 6h total)
            ("6h_shifted", False, time(7,0), time(13,0), 360, 360, 0),
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
            actual_worked = ponto.worked_minutes
            actual_target = target
            actual_balance = user.total_balance
            print(f"DEBUG: {name} | worked: {actual_worked}, target: {actual_target}, balance: {actual_balance}, complete: {ponto.is_complete}")
            self.assertEqual(actual_worked, worked, f"Failed worked_minutes for {name}")
            # Ensure day is marked complete
            self.assertTrue(ponto.is_complete, f"Day not complete for {name}")
            # Note: User.total_balance uses its own target logic
            self.assertEqual(actual_balance, expected_bal, f"Failed balance for {name}")

if __name__ == "__main__":
    unittest.main()
