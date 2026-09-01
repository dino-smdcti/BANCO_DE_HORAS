from sqlalchemy import create_engine, inspect, text

from scripts.run_migrations import run_all_migrations


def test_run_all_migrations_on_sqlite_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    run_all_migrations(engine)
    run_all_migrations(engine)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "users" in tables
    assert "daily_pontos" in tables
    assert "audit_logs" in tables
    assert "absence_state" in tables

    with engine.connect() as conn:
        index_names = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type = 'index'"))}
        assert "ix_daily_pontos_entry_date" in index_names
        assert "ix_users_role" in index_names