"""EquityHistorical fetcher tests (D79 19.6) — DB-backed pricing via fake conn."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from openbb_obligacje import obligacje_provider
from openbb_obligacje.models.fixedincome_historical import (
    CpiStaleError,
    FixedIncomeHistoricalFetcher,
    ObligacjeEquityHistoricalData,
    ObligacjeEquityHistoricalQueryParams,
)

_CPI_12M = "ORDER BY date"
_LATEST_CPI = "MAX(date)"


def _bond_row(
    symbol="EDO0936",
    series_code="EDO",
    issue_date=date(2026, 9, 1),
    maturity_date=date(2036, 9, 1),
    term_months=120,
    rate_rule="cpi_12m+margin",
    margin="2.00",
    fee_b="3.00",
):
    return (
        symbol,
        "EDO0936",
        series_code,
        issue_date,
        maturity_date,
        term_months,
        rate_rule,
        Decimal(margin),
        Decimal(fee_b),
        Decimal("100.00"),
    )


def _cpi_row(day, value="3.00"):
    return (day, Decimal(value))


def test_transform_query_defaults():
    q = FixedIncomeHistoricalFetcher.transform_query({"symbol": "EDO0936"})
    assert isinstance(q, ObligacjeEquityHistoricalQueryParams)
    assert q.symbol == "EDO0936"
    assert q.start_date is None
    assert q.end_date is None


def test_transform_query_camel_case_alias():
    q = FixedIncomeHistoricalFetcher.transform_query(
        {"symbol": "EDO0936", "startDate": "2026-09-01", "end_date": "2026-12-01"}
    )
    assert q.start_date == date(2026, 9, 1)
    assert q.end_date == date(2026, 12, 1)


def test_extract_data_unknown_symbol_returns_empty(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {"WHERE symbol = %s": []}
    q = FixedIncomeHistoricalFetcher.transform_query({"symbol": "XXX0000"})
    assert FixedIncomeHistoricalFetcher.extract_data(q) == []


def test_extract_data_prices_cpi_linked_series(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {
        "WHERE symbol = %s": [_bond_row()],
        _CPI_12M: [_cpi_row(date(2026, 8, 31), "3.00"), _cpi_row(date(2026, 9, 30), "3.50")],
        _LATEST_CPI: [(date(2026, 9, 30),)],
    }
    q = FixedIncomeHistoricalFetcher.transform_query(
        {"symbol": "EDO0936", "start_date": "2026-09-01", "end_date": "2026-09-02"}
    )
    rows = FixedIncomeHistoricalFetcher.extract_data(q)
    assert len(rows) == 2
    assert rows[0]["date"] == "2026-09-01"
    assert rows[0]["close"] == 100.0
    assert rows[1]["open"] == 100.0
    assert rows[1]["close"] == 100.0


def test_extract_data_defaults_to_full_term_for_fixed_series(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {
        "WHERE symbol = %s": [
            _bond_row(
                symbol="OTS0126",
                series_code="OTS",
                issue_date=date(2026, 9, 1),
                maturity_date=date(2026, 12, 1),
                term_months=3,
                rate_rule="fixed",
                margin="1.50",
                fee_b="0.00",
            )
        ],
        _CPI_12M: [],
        _LATEST_CPI: [],
    }
    q = FixedIncomeHistoricalFetcher.transform_query({"symbol": "OTS0126"})
    rows = FixedIncomeHistoricalFetcher.extract_data(q)
    assert len(rows) == 92  # 2026-09-01 .. 2026-12-01 inclusive
    assert rows[0]["date"] == "2026-09-01"
    assert rows[0]["close"] == 100.0
    assert rows[-1]["date"] == "2026-12-01"
    assert rows[-1]["close"] == 100.38


def test_extract_data_stale_cpi_raises(fake_conn):
    stale = date.today() - timedelta(days=60)
    fake_conn.cursor_obj._rows_by_sql = {
        "WHERE symbol = %s": [_bond_row()],
        _CPI_12M: [_cpi_row(stale)],
        _LATEST_CPI: [(stale,)],
    }
    q = FixedIncomeHistoricalFetcher.transform_query({"symbol": "EDO0936"})
    with pytest.raises(CpiStaleError, match="is stale"):
        FixedIncomeHistoricalFetcher.extract_data(q)


def test_extract_data_empty_cpi_raises(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {
        "WHERE symbol = %s": [_bond_row()],
        _CPI_12M: [],
        _LATEST_CPI: [(None,)],
    }
    q = FixedIncomeHistoricalFetcher.transform_query({"symbol": "EDO0936"})
    with pytest.raises(CpiStaleError, match="is empty"):
        FixedIncomeHistoricalFetcher.extract_data(q)


def test_extract_data_closes_connection(fake_conn):
    fake_conn.cursor_obj._rows_by_sql = {"WHERE symbol = %s": []}
    q = FixedIncomeHistoricalFetcher.transform_query({"symbol": "XXX0000"})
    FixedIncomeHistoricalFetcher.extract_data(q)
    assert fake_conn.closed


def test_transform_data_round_trip():
    q = FixedIncomeHistoricalFetcher.transform_query({"symbol": "EDO0936"})
    rows = [
        {
            "date": "2026-09-01",
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 0,
        }
    ]
    out = FixedIncomeHistoricalFetcher.transform_data(q, rows)
    assert isinstance(out[0], ObligacjeEquityHistoricalData)
    assert out[0].close == 100.0
    assert out[0].date == date(2026, 9, 1)


def test_registered_under_equity_historical():
    assert obligacje_provider.fetcher_dict["EquityHistorical"] is FixedIncomeHistoricalFetcher