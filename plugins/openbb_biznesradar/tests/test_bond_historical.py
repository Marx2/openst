"""Bond (Catalyst) fetcher tests (D77 16.4) — full path through EquityHistoricalFetcher."""

from datetime import date

from openbb_biznesradar.models.bond_historical import parse_bond_row
from openbb_biznesradar.models.equity_historical import (
    BiznesRadarEquityHistoricalData,
    EquityHistoricalFetcher,
)


def _fetch(httpx_mock, params, pages):
    httpx_mock(pages)
    query = EquityHistoricalFetcher.transform_query(params)
    data = EquityHistoricalFetcher.extract_data(query)
    return EquityHistoricalFetcher.transform_data(query, data)


def test_bond_fetcher_happy_path(httpx_mock, read_fixture):
    # `.WA` exchange suffix is stripped, bond (7-col) scraper dispatch kicks in
    rows = _fetch(
        httpx_mock,
        {"symbol": "BST0327.WA", "start_date": date(2000, 1, 1), "end_date": date(2026, 12, 31)},
        [(read_fixture("BST0327.html"), 200)],
    )
    assert len(rows) == 50
    assert isinstance(rows[0], BiznesRadarEquityHistoricalData)
    assert rows[0].date == date(2026, 9, 10)
    assert rows[0].open == rows[0].high == rows[0].low == rows[0].close == 101.30
    assert rows[0].volume == 60
    # a row with genuinely distinct OHLCV: 09.09.2026 open/high 101.50, low 101.00
    assert rows[1].date == date(2026, 9, 9)
    assert rows[1].open == 101.50
    assert rows[1].high == 101.50
    assert rows[1].low == 101.00
    assert rows[1].close == 101.00
    assert rows[1].volume == 45


def test_bond_fetcher_range_filter(httpx_mock, read_fixture):
    rows = _fetch(
        httpx_mock,
        {"symbol": "BST0327", "start_date": date(2026, 9, 9), "end_date": date(2026, 9, 10)},
        [(read_fixture("BST0327.html"), 200)],
    )
    assert [r.date for r in rows] == [date(2026, 9, 10), date(2026, 9, 9)]
    assert [r.volume for r in rows] == [60, 45]


def test_bond_fetcher_empty_result_in_range(httpx_mock, read_fixture):
    rows = _fetch(
        httpx_mock,
        {"symbol": "BST0327", "start_date": date(2030, 1, 1), "end_date": date(2030, 12, 31)},
        [(read_fixture("BST0327.html"), 200)],
    )
    assert rows == []


def test_bond_fetcher_default_bounds_when_dates_missing(httpx_mock, read_fixture):
    rows = _fetch(
        httpx_mock,
        {"symbol": "BST0327"},
        [(read_fixture("BST0327.html"), 200)],
    )
    assert len(rows) == 50


def test_parse_bond_row_maps_to_ohlcv():
    row = parse_bond_row(
        {
            "date": date(2026, 9, 10),
            "open": 101.30,
            "high": 101.30,
            "low": 101.30,
            "close": 101.30,
            "volume": 60,
        }
    )
    assert row == {
        "date": date(2026, 9, 10),
        "open": 101.30,
        "high": 101.30,
        "low": 101.30,
        "close": 101.30,
        "volume": 60,
    }