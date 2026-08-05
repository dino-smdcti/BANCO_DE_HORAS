"""Smoke check that the app actually works against the configured Neon DB.

Reads .env (DATABASE_URL), then:
  1. Connects and lists tables.
  2. Reads live data through the app's unit of work.
  3. Exercises a write + rollback (no data left behind).
  4. Boots the Flask test client and hits public routes.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

EXPECTED_TABLES = {
    "users",
    "work_schedules",
    "daily_pontos",
    "correction_requests",
    "vacations",
    "notifications",
    "journey_types",
    "audit_logs",
    "holidays",
    "company_settings",
}


def main():
    failures = 0

    def check(label, ok, detail=""):
        nonlocal failures
        status = "OK  " if ok else "FAIL"
        print(f"[{status}] {label}{' -- ' + detail if detail else ''}")
        if not ok:
            failures += 1

    from src.entrypoints.flask_app import _database_url, app
    from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork

    url = _database_url()
    check("DATABASE_URL points at Neon", "neon.tech" in url, url.split("@")[1].split("?")[0])

    import sqlalchemy as sa

    engine = sa.create_engine(url)
    with engine.connect() as conn:
        version = conn.execute(sa.text("select version()")).scalar()
        check("postgres reachable", version.lower().startswith("postgresql"), version.split(" on ")[0])

        tables = set(conn.execute(sa.text("select table_name from information_schema.tables where table_schema = 'public'")).scalars())
        missing = EXPECTED_TABLES - tables
        check("all app tables present", not missing, "missing: %s" % sorted(missing) if missing else "%d tables" % len(tables))

        user_count = conn.execute(sa.text("select count(*) from users")).scalar()
        check("users readable", isinstance(user_count, int), f"{user_count} users")

        conn.execute(sa.text("select 1"))
        conn.execute(sa.text("create temp table _smoke(id int)"))
        conn.execute(sa.text("insert into _smoke values (42)"))
        check("temp write works", True)

    with SqlAlchemyUnitOfWork() as uow:
        sample = uow.users.get_user_by_email("admin@admin.com")
        check("unit of work reads Neon", sample is not None, f"id={sample.user_id} role={sample.role}")

        before = uow.session.execute(sa.text("select count(*) from audit_logs")).scalar()
        uow.record_action(sample.user_id, "DB_SMOKE_TEST", details="verify_db smoke check")
        uow.session.flush()
        uow.rollback()
        after = uow.session.execute(sa.text("select count(*) from audit_logs")).scalar()
        check("write + rollback leaves no trace", before == after, f"{before} -> {after}")

    client = app.test_client()
    for path in ("/", "/login"):
        resp = client.get(path)
        check(f"GET {path} responds", resp.status_code in (200, 302), f"status={resp.status_code}")

    print()
    if failures:
        print(f"{failures} check(s) FAILED")
        sys.exit(1)
    print("ALL CHECKS PASSED - app is working against the Neon database.")


if __name__ == "__main__":
    main()
