from sqlalchemy import create_engine, inspect

from src.adapters.orm import metadata, start_mappers

EXPECTED_INDEXES = {
    "ix_daily_pontos_entry_date",
    "ix_daily_pontos_user_entry_date",
    "ix_audit_logs_user_id",
    "ix_audit_logs_timestamp",
    "ix_notifications_user_created",
    "ix_correction_requests_status",
    "ix_vacations_user_dates",
    "ix_attestations_user_dates",
    "ix_users_role",
}


class TestIndexes:
    def test_all_phase3_indexes_created(self):
        engine = create_engine("sqlite:///:memory:")
        start_mappers()
        metadata.create_all(engine)
        insp = inspect(engine)
        present = set()
        for table in insp.get_table_names():
            for index in insp.get_indexes(table):
                present.add(index["name"])
        for name in EXPECTED_INDEXES:
            assert name in present, f"missing index {name}"
