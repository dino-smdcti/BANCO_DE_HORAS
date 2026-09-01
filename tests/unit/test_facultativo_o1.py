from datetime import date

from src.domain.model import Facultativo
from src.service_layer.absence_processor import _is_facultativo

FAC = [Facultativo(start_date=date(2026, 5, 1), end_date=date(2026, 5, 15), description="t")]


class TestFacultativoO1:
    def test_within_range(self):
        assert _is_facultativo(date(2026, 5, 10), FAC) is True

    def test_before_range(self):
        assert _is_facultativo(date(2026, 4, 30), FAC) is False

    def test_after_range(self):
        assert _is_facultativo(date(2026, 5, 16), FAC) is False

    def test_boundaries_inclusive(self):
        assert _is_facultativo(date(2026, 5, 1), FAC) is True
        assert _is_facultativo(date(2026, 5, 15), FAC) is True

    def test_no_facultativos(self):
        assert _is_facultativo(date(2026, 5, 10), []) is False
