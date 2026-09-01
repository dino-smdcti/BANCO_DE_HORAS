from datetime import date
from unittest.mock import patch

import src.service_layer.absence_processor as ap


def test_last_check_defaults_when_empty(uow):
    with patch.object(ap, "IS_TESTING", False), patch.object(ap, "_test_last_check", None):
        with uow:
            assert ap.get_last_check(uow) == ap.ABSENCE_DEFAULT_LAST_CHECK_DATE


def test_last_check_round_trip_persists(uow):
    with patch.object(ap, "IS_TESTING", False), patch.object(ap, "_test_last_check", None):
        with uow:
            ap.set_last_check(uow, date(2026, 5, 12))
        with uow:
            assert ap.get_last_check(uow) == date(2026, 5, 12)