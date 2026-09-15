"""Thin Postgres access for openst (D79 — retail savings bonds).

Reads ``DATABASE_URL`` from env and exposes ``get_conn()`` (plain psycopg2, no
ORM). A boot-time migration runner applies ``migrations/*.sql`` exactly once,
journaled in ``openst.schema_migrations`` — mirroring the per-module journal
pattern the portfoliost TypeScript modules get from Drizzle (see
portfoliost/docs/proposals/database-schema-migrations.md). openst stays
functional without a database: callers guard on ``database_url()`` presence.
"""

from __future__ import annotations

import logging
import os
import pathlib

logger = logging.getLogger("openst")

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"


def database_url() -> str | None:
    return os.environ.get("DATABASE_URL")


def get_conn():
    """Open a plain psycopg2 connection. Requires ``DATABASE_URL`` to be set."""
    import psycopg2

    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(url)


def _ensure_journal(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE SCHEMA IF NOT EXISTS openst;
            CREATE TABLE IF NOT EXISTS openst.schema_migrations (
                name        TEXT PRIMARY KEY,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )
        cur.execute("SELECT name FROM openst.schema_migrations")
        return {row[0] for row in cur.fetchall()}


def _pending(migrations_dir: pathlib.Path, applied: set[str]) -> list[tuple[str, str]]:
    pending = []
    for path in sorted(migrations_dir.glob("*.sql")):
        if path.stem not in applied:
            pending.append((path.stem, path.read_text()))
    return pending


def migrate(conn=None, migrations_dir: pathlib.Path | None = None) -> list[str]:
    """Apply pending migrations from ``migrations/``, journaling each exactly once.

    Idempotent: already-applied migrations are skipped, so calling twice — or on
    every boot — is a no-op. Returns the full list of applied migration names.

    Each migration runs in its own transaction together with its journal insert;
    a failed migration rolls back and is retried on the next call.
    """
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    try:
        applied = _ensure_journal(conn)
        conn.commit()
        pending = _pending(migrations_dir or MIGRATIONS_DIR, applied)
        for name, sql in pending:
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO openst.schema_migrations (name) VALUES (%s) "
                    "ON CONFLICT (name) DO NOTHING",
                    (name,),
                )
            conn.commit()
            logger.info("applied migration %s", name)
            applied.append(name)
        return applied
    finally:
        if own_conn:
            conn.close()