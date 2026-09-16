"""EquityInfo (profile) fetcher tests (D79 19.6) — catalogue lookup via fake conn."""

from datetime import date
from decimal import Decimal

from openbb_obligacje import obligacje_provider
from openbb_obligacje.models.fixedincome_profile import (
    FixedIncomeProfileFetcher,
    ObligacjeEquityInfoData,
)


def _cell(symbol="EDO0936"):
    return (
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


def test_transform_query():
    q = FixedIncomeProfileFetcher.transform_query({"symbol": "EDO0936"})
    assert q.symbol == "EDO0936"


def test_transform_query_uppercases_symbol():
    q = FixedIncomeProfileFetcher.transform_query({"symbol": "edo0936"})
    assert q.symbol == "EDO0936"


def test_extract_data_unknown_symbol_returns_empty_list(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {"WHERE symbol = %s": []}
    q = FixedIncomeProfileFetcher.transform_query({"symbol": "XXX0000"})
    assert FixedIncomeProfileFetcher.extract_data(q) == []


def test_extract_data_returns_catalogue_row(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {"WHERE symbol = %s": [_cell()]}
    q = FixedIncomeProfileFetcher.transform_query({"symbol": "EDO0936"})
    rows = FixedIncomeProfileFetcher.extract_data(q)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "EDO0936"
    assert rows[0]["rate_rule"] == "cpi_12m+margin"
    assert rows[0]["maturity_date"] == date(2036, 9, 1)
    assert rows[0]["margin"] == Decimal("2.00")


def test_transform_data_round_trip():
    q = FixedIncomeProfileFetcher.transform_query({"symbol": "EDO0936"})
    row = {
        "symbol": "EDO0936",
        "name": "EDO0936",
        "series_code": "EDO",
        "issue_date": date(2026, 9, 1),
        "maturity_date": date(2036, 9, 1),
        "term_months": 120,
        "rate_rule": "cpi_12m+margin",
        "margin": Decimal("2.00"),
        "fee_b": Decimal("3.00"),
        "nominal": Decimal("100.00"),
    }
    out = FixedIncomeProfileFetcher.transform_data(q, [row])
    assert isinstance(out[0], ObligacjeEquityInfoData)
    assert out[0].symbol == "EDO0936"
    assert out[0].maturity_date == date(2036, 9, 1)
    assert out[0].rate_rule == "cpi_12m+margin"
    assert out[0].margin == Decimal("2.00")


def test_registered_under_equity_info():
    assert obligacje_provider.fetcher_dict["EquityInfo"] is FixedIncomeProfileFetcher