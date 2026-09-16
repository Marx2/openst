"""Shared fixtures for the obligacje fetcher tests (D79 19.6) — fake Postgres conn.

The fetchers read Postgres through ``openbb_obligacje.store``; every store
function accepts an optional ``conn`` and falls back to ``store.get_conn()``.
This fixture swaps ``get_conn`` for a fake connection whose cursor serves canned
rows keyed by SQL substring, so the fetcher tests exercise the real store SQL
paths without a database.
"""

from __future__ import annotations

import pytest

from openbb_obligacje import store


class _FakeCursor:
    """Stub psycopg2 cursor — returns canned rows based on the SQL text."""

    def __init__(self, rows_by_sql: dict[str, list[tuple]] | None = None):
        self._rows_by_sql = rows_by_sql or {}
        self._result: list = []
        self.sql: str | None = None
        self.params = None

    def execute(self, sql: str, params=None):
        self.sql = sql
        self.params = params
        for needle, rows in self._rows_by_sql.items():
            if needle in sql:
                self._result = list(rows)
                return
        self._result = []

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return self._result

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class _FakeConn:
    """Stub psycopg2 connection wrapping a :class:`_FakeCursor`."""

    def __init__(self):
        self.cursor_obj = _FakeCursor()
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


@pytest.fixture
def fake_conn(monkeypatch):
    """Install a fake connection on ``store.get_conn`` and return it.

    Seed rows in the test via ``fake_conn.cursor_obj._rows_by_sql`` using
    SQL-substring keys:

        fake_conn.cursor_obj._rows_by_sql = {"WHERE symbol = %s": [(_row,)]}
    """
    conn = _FakeConn()
    monkeypatch.setattr(store, "get_conn", lambda: conn)
    return conn