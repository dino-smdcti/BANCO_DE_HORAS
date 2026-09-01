import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from src.service_layer.unit_of_work import resolve_database_url

INDEX_MIGRATIONS = [
    "CREATE INDEX IF NOT EXISTS ix_daily_pontos_entry_date ON daily_pontos (entry_date);",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_daily_pontos_user_entry_date ON daily_pontos (user_id, entry_date);",
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id);",
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_timestamp ON audit_logs (timestamp);",
    "CREATE INDEX IF NOT EXISTS ix_notifications_user_created ON notifications (user_id, created_at);",
    "CREATE INDEX IF NOT EXISTS ix_correction_requests_status ON correction_requests (status);",
    "CREATE INDEX IF NOT EXISTS ix_vacations_user_dates ON vacations (user_id, start_date, end_date);",
    "CREATE INDEX IF NOT EXISTS ix_attestations_user_dates ON attestations (user_id, start_date, end_date);",
    "CREATE INDEX IF NOT EXISTS ix_users_role ON users (role);",
    "CREATE INDEX IF NOT EXISTS ix_users_team_id ON users (team_id);",
]


def run_index_migrations(engine):
    with engine.connect() as conn:
        for sql in INDEX_MIGRATIONS:
            try:
                print(f"Executing: {sql}")
                conn.execute(text(sql))
                conn.commit()
                print("Success.")
            except Exception as e:
                print(f"Error executing migration: {e}")
                conn.rollback()


def main():
    load_dotenv()
    print(f"Connecting to database...")
    engine = create_engine(resolve_database_url())
    run_index_migrations(engine)
    print("Index migrations completed.")


if __name__ == "__main__":
    main()