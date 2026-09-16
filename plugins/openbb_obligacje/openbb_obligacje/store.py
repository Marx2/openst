"""Postgres read access for the obligacje fetchers (D79 19.6).

Reads ``openst.bond_series`` and ``openst.cpi_12m`` from the shared PGO cluster
(via ``src.db`` — the same thin psycopg2 helper the openst importers use). Every
function takes an optional ``conn`` so the fetchers can share one connection per
request and tests can inject a fake one; with ``conn=None`` a connection is
opened (and closed) locally.
"""

from __future__ import annotations

from decimal import Decimal

from openbb_obligacje.engine import BondSeries, CpiRow

_BOND_COLUMNS = (
    "symbol, name, series_code, issue_date, maturity_date, term_months, "
    "rate_rule, margin, fee_b, nominal"
)


def get_conn():
    """Open a Postgres connection, matching ``src.db.get_conn()`` semantics."""
    from src import db

    return db.get_conn()


def _row_to_bond_series(row: tuple) -> BondSeries:
    (
        symbol,
        name,
        series_code,
        issue_date,
        maturity_date,
        term_months,
        rate_rule,
        margin,
        fee_b,
        nominal,
    ) = row
    return BondSeries(
        symbol=symbol,
        name=name,
        series_code=series_code,
        issue_date=issue_date,
        maturity_date=maturity_date,
        term_months=term_months,
        rate_rule=rate_rule,
        margin=Decimal(margin),
        fee_b=Decimal(fee_b),
        nominal=Decimal(nominal),
    )


def fetch_bond_series(symbol: str, conn=None) -> BondSeries | None:
    """Load one emission from ``openst.bond_series`` by exact symbol.

    Returns ``None`` when the symbol is not in the catalogue.
    """
    own = conn is None
    if own:
        conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_BOND_COLUMNS} FROM openst.bond_series "
                "WHERE symbol = %s",
                (symbol,),
            )
            row = cur.fetchone()
            return _row_to_bond_series(row) if row else None
    finally:
        if own:
            conn.close()


def search_bond_series(query: str, is_symbol: bool, conn=None) -> list[BondSeries]:
    """Find emissions whose symbol starts with ``query`` (or whose name contains it).

    With ``is_symbol`` only the symbol prefix is matched; otherwise the name
    substring is searched too. Ordered by symbol for stable output.
    """
    own = conn is None
    if own:
        conn = get_conn()
    try:
        with conn.cursor() as cur:
            if is_symbol:
                cur.execute(
                    f"SELECT {_BOND_COLUMNS} FROM openst.bond_series "
                    "WHERE symbol ILIKE %s ORDER BY symbol",
                    (f"{query}%",),
                )
            else:
                cur.execute(
                    f"SELECT {_BOND_COLUMNS} FROM openst.bond_series "
                    "WHERE symbol ILIKE %s OR name ILIKE %s ORDER BY symbol",
                    (f"{query}%", f"%{query}%"),
                )
            return [_row_to_bond_series(row) for row in cur.fetchall()]
    finally:
        if own:
            conn.close()


def fetch_cpi_rows(conn=None) -> list[CpiRow]:
    """Load the full 12-month CPI history, oldest first."""
    own = conn is None
    if own:
        conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT date, value FROM openst.cpi_12m ORDER BY date")
            return [CpiRow(day, Decimal(value)) for day, value in cur.fetchall()]
    finally:
        if own:
            conn.close()


def latest_cpi_date(conn=None):
    """The date of the newest ``openst.cpi_12m`` row, or ``None`` when empty."""
    own = conn is None
    if own:
        conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(date) FROM openst.cpi_12m")
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        if own:
            conn.close()