"""Automated migration runner for deploy-time schema sync.

Runs on every deployment (and cold start via Vercel build). It is idempotent:
- creates any missing tables from the SQLAlchemy metadata,
- applies the index statements (safe on SQLite and Postgres),
- applies the Postgres ALTER statements only when connected to Postgres.

Exit/behavior: the Vercel /tmp SQLite fallback requires ALLOW_EPHEMERAL_SQLITE
and still logs loudly that it is not durable. Database URLs are printed without
credentials to avoid leaking secrets into logs.
"""
import sys

from sqlalchemy import create_engine

from dotenv import load_dotenv

from src.adapters.orm import metadata
from src.service_layer.unit_of_work import resolve_database_url
from scripts.migrations.apply_migrations import run_base_migrations
from scripts.migrations.apply_indexes import run_index_migrations


def _safe_url_for_logging(database_url):
        scheme_end = database_url.find("://")
        if scheme_end == -1:
                return database_url
        rest = database_url[scheme_end + 3:]
        host = rest.split("@")[-1].split("/")[0]
        return f"{database_url[:scheme_end]}://{host or '(unknown)'}"


def run_all_migrations(engine):
        print("Creating missing tables from SQLAlchemy metadata...")
        metadata.create_all(engine)
        print("Applying indexes...")
        run_index_migrations(engine)
        if engine.dialect.name == "postgresql":
                print("Postgres detected: applying base ALTER migrations...")
                run_base_migrations(engine)
        else:
                print("SQLite detected: base ALTER migrations skipped (tables are created by create_all).")


def main():
        load_dotenv()
        database_url = resolve_database_url()
        print(f"Running migrations against {_safe_url_for_logging(database_url)}")
        engine = create_engine(database_url)
        run_all_migrations(engine)
        print("All migrations completed.")


if __name__ == "__main__":
        try:
                main()
        except Exception as error:
                print(f"Migration run failed: {error}", file=sys.stderr)
                raise