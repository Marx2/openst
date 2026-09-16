"""EquitySearch fetcher tests (D79 19.6) — catalogue search via fake conn."""

from datetime import date
from decimal import Decimal

from openbb_obligacje import obligacje_provider
from openbb_obligacje.models.fixedincome_search import (
    FixedIncomeSearchFetcher,
    ObligacjeEquitySearchData,
)

_SEARCH_NAME = "OR name ILIKE"
_SEARCH_SYMBOL = "WHERE symbol ILIKE"


def _row(symbol="EDO0936", series_code="EDO", maturity=date(2036, 9, 1)):
    return (
        symbol,
        "DOBROCZE EDO 10-letnie",
        series_code,
        date(2026, 9, 1),
        maturity,
        120,
        "cpi_12m+margin",
        Decimal("2.00"),
        Decimal("3.00"),
        Decimal("100.00"),
    )


def test_transform_query_defaults():
    q = FixedIncomeSearchFetcher.transform_query({"query": "EDO"})
    assert q.query == "EDO"
    assert q.is_symbol is False


def test_transform_query_symbol_alias():
    q = FixedIncomeSearchFetcher.transform_query({"symbol": "EDO0936"})
    assert q.query == "EDO0936"


def test_extract_data_empty_query_returns_empty(fake_conn):
    q = FixedIncomeSearchFetcher.transform_query({"query": ""})
    assert FixedIncomeSearchFetcher.extract_data(q) == []


def test_extract_data_searches_symbol_prefix_by_default(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {
        _SEARCH_NAME: [_row(), _row("EDO1036", maturity=date(2036, 10, 1))]
    }
    q = FixedIncomeSearchFetcher.transform_query({"query": "EDO"})
    rows = FixedIncomeSearchFetcher.extract_data(q)
    assert [r["symbol"] for r in rows] == ["EDO0936", "EDO1036"]
    assert rows[0]["maturity_date"] == date(2036, 9, 1)
    assert "OR name ILIKE" in fake_conn.cursor_obj.sql


def test_extract_data_is_symbol_matches_symbol_only(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {
        _SEARCH_SYMBOL: [_row()]
    }
    q = FixedIncomeSearchFetcher.transform_query({"query": "EDO0936", "is_symbol": True})
    rows = FixedIncomeSearchFetcher.extract_data(q)
    assert [r["symbol"] for r in rows] == ["EDO0936"]
    assert "OR name ILIKE" not in fake_conn.cursor_obj.sql


def test_extract_data_no_matches_returns_empty(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {_SEARCH_NAME: []}
    q = FixedIncomeSearchFetcher.transform_query({"query": "ZZZ"})
    assert FixedIncomeSearchFetcher.extract_data(q) == []


def test_transform_data_round_trip():
    q = FixedIncomeSearchFetcher.transform_query({"query": "EDO"})
    rows = [
        {
            "symbol": "EDO0936",
            "name": "EDO0936",
            "maturity_date": date(2036, 9, 1),
        }
    ]
    out = FixedIncomeSearchFetcher.transform_data(q, rows)
    assert isinstance(out[0], ObligacjeEquitySearchData)
    assert out[0].symbol == "EDO0936"
    assert out[0].maturity_date == date(2036, 9, 1)


def test_registered_under_equity_search():
    assert obligacje_provider.fetcher_dict["EquitySearch"] is FixedIncomeSearchFetcher