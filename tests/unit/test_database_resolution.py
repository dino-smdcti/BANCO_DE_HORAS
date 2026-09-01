import pytest

from src.config import LOCAL_SQLITE_URL, VERCEL_SQLITE_URL
from src.service_layer.unit_of_work import resolve_database_url


def test_defaults_to_local_sqlite():
    assert resolve_database_url({}) == LOCAL_SQLITE_URL


def test_database_url_wins():
    assert resolve_database_url({"DATABASE_URL": "postgresql://u:p@host/db"}) == "postgresql://u:p@host/db"


def test_postgres_url_is_normalized():
    assert resolve_database_url({"POSTGRES_URL": "postgres://u:p@host/db"}) == "postgresql://u:p@host/db"


def test_database_url_beats_vercel_flag():
    assert resolve_database_url({"VERCEL": "1", "DATABASE_URL": "postgresql://u:p@host/db"}) == "postgresql://u:p@host/db"


def test_vercel_without_database_url_fails_fast(capsys):
    with pytest.raises(RuntimeError, match="ALLOW_EPHEMERAL_SQLITE"):
        resolve_database_url({"VERCEL": "1"})


def test_vercel_ephemeral_fallback_logs_loudly(capsys):
    assert resolve_database_url({"VERCEL": "1", "ALLOW_EPHEMERAL_SQLITE": "1"}) == VERCEL_SQLITE_URL
    captured = capsys.readouterr()
    assert "ephemeral" in captured.err.lower()