"""store module tests (D79 19.6) — SQL paths against the fake connection."""

from datetime import date
from decimal import Decimal

from openbb_obligacje import store
from openbb_obligacje.engine import BondSeries, CpiRow


def _cells(symbol="EDO0936"):
    return [
        (
            symbol,
            "EDO0936",
            "EDO",
            date(2026, 9, 1),
            date(2036, 9, 1),
            120,
            "cpi_12m+margin",
            Decimal("2.00"),
            Decimal("3.00"),
            Decimal("100.00"),
        )
    ]


def _cpi_cells():
    return [(date(2026, 8, 31), Decimal("3.00")), (date(2026, 9, 30), Decimal("3.50"))]


def test_fetch_bond_series_maps_all_fields(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {"WHERE symbol = %s": _cells()}
    bond = store.fetch_bond_series("EDO0936")
    assert isinstance(bond, BondSeries)
    assert bond.symbol == "EDO0936"
    assert bond.maturity_date == date(2036, 9, 1)
    assert bond.term_months == 120
    assert bond.rate_rule == "cpi_12m+margin"
    assert bond.margin == Decimal("2.00")
    assert bond.fee_b == Decimal("3.00")
    assert bond.nominal == Decimal("100.00")


def test_fetch_bond_series_unknown_returns_none(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {"WHERE symbol = %s": []}
    assert store.fetch_bond_series("XXX0000") is None


def test_fetch_bond_series_keeps_own_connection_lifecycle(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {"WHERE symbol = %s": _cells()}
    store.fetch_bond_series("EDO0936")
    assert fake_conn.closed


def test_fetch_bond_series_does_not_close_shared_conn(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {"WHERE symbol = %s": _cells()}
    store.fetch_bond_series("EDO0936", conn=fake_conn)
    assert not fake_conn.closed


def test_search_default_queries_symbol_and_name(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {"OR name ILIKE": _cells()}
    bonds = store.search_bond_series("EDO", is_symbol=False)
    assert [b.symbol for b in bonds] == ["EDO0936"]
    assert "OR name ILIKE" in fake_conn.cursor_obj.sql


def test_search_is_symbol_queries_symbol_only(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {"WHERE symbol ILIKE": _cells()}
    bonds = store.search_bond_series("EDO", is_symbol=True)
    assert [b.symbol for b in bonds] == ["EDO0936"]
    assert "OR name ILIKE" not in fake_conn.cursor_obj.sql
    assert fake_conn.cursor_obj.params == ("EDO%",)


def test_fetch_cpi_rows_maps_rows(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {"ORDER BY date": _cpi_cells()}
    rows = store.fetch_cpi_rows()
    assert rows == [
        CpiRow(date(2026, 8, 31), Decimal("3.00")),
        CpiRow(date(2026, 9, 30), Decimal("3.50")),
    ]


def test_latest_cpi_date(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {"MAX(date)": [(date(2026, 9, 30),)]}
    assert store.latest_cpi_date() == date(2026, 9, 30)


def test_latest_cpi_date_empty(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {"MAX(date)": []}
    assert store.latest_cpi_date() is None