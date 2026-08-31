import pytest
from datetime import date
from sqlalchemy.exc import IntegrityError

from src.domain.model import User, UserRole, DailyPonto

DAY = date(2026, 5, 4)


class TestDailyPontoUnique:
        def test_duplicate_user_entry_date_rejected(self, uow):
                with uow:
                        user = User(email="dup@test.com", password_hash="!", role=UserRole.EMPLOYEE)
                        uow.session.add(user)
                        uow.commit()
                        uid = user.user_id
                with pytest.raises(IntegrityError):
                        with uow:
                                user2 = uow.users.get_user_by_id(uid)
                                user2.time_entries.append(DailyPonto(user_id=uid, entry_date=DAY))
                                uow.commit()
                                user2.time_entries.append(DailyPonto(user_id=uid, entry_date=DAY))
                                uow.commit()

        def test_different_entry_dates_allowed(self, uow):
                with uow:
                        user = User(email="dup2@test.com", password_hash="!", role=UserRole.EMPLOYEE)
                        uow.session.add(user)
                        uow.commit()
                        uid = user.user_id
                with uow:
                        user2 = uow.users.get_user_by_id(uid)
                        user2.time_entries.append(DailyPonto(user_id=uid, entry_date=DAY))
                        user2.time_entries.append(DailyPonto(user_id=uid, entry_date=date(2026, 5, 5)))
                        uow.commit()
                        points = [p.entry_date for p in user2.time_entries]
                assert set(points) == {DAY, date(2026, 5, 5)}
