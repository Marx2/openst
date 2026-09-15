"""DB access + migration tests (D79).

The migration-idempotency tests need a live Postgres: they run against the
compose ``postgres`` service (``DATABASE_URL`` set in the test profile) and are
skipped when it is absent. Mirrors the PGlite-replay of the real journal in the
portfoliost TypeScript modules (database-schema-migrations.md).
"""

import pytest

from src import db

needs_pg = pytest.mark.skipif(
    not db.database_url(),
    reason="DATABASE_URL not set (run via docker compose --profile test)",
)


def _journal(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM openst.schema_migrations ORDER BY name")
        return [row[0] for row in cur.fetchall()]


@pytest.fixture
def conn():
    c = db.get_conn()
    yield c
    c.close()


@needs_pg
def test_get_conn_defaults_to_database_url(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user")
        dbname, user = cur.fetchone()
    assert dbname == "openst"
    assert user == "openst"


@needs_pg
def test_migrate_is_idempotent(conn):
    first = db.migrate(conn=conn)
    second = db.migrate(conn=conn)
    assert first == second
    assert "001_openst_schema" in _journal(conn)


@needs_pg
def test_migrate_creates_tables(conn):
    db.migrate(conn=conn)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'openst'
            ORDER BY tablename
            """
        )
        tables = [row[0] for row in cur.fetchall()]
    assert "cpi_12m" in tables
    assert "bond_series" in tables
    assert "schema_migrations" in tables


def test_get_conn_raises_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        db.get_conn()


def test_migrate_requires_connection(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        db.migrate()