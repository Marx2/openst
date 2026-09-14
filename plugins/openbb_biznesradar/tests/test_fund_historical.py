"""Fund (TFI/FIZ) fetcher tests (D77 16.4) — full path through EquityHistoricalFetcher."""

from datetime import date

from openbb_biznesradar.models.equity_historical import (
    BiznesRadarEquityHistoricalData,
    EquityHistoricalFetcher,
)
from openbb_biznesradar.models.fund_historical import parse_fund_row


def _fetch(httpx_mock, params, pages):
    httpx_mock(pages)
    query = EquityHistoricalFetcher.transform_query(params)
    data = EquityHistoricalFetcher.extract_data(query)
    return EquityHistoricalFetcher.transform_data(query, data)


def test_fund_fetcher_happy_path(httpx_mock, read_fixture):
    rows = _fetch(
        httpx_mock,
        {"symbol": "NNEP25.TFI", "start_date": date(2000, 1, 1), "end_date": date(2026, 12, 31)},
        [(read_fixture("NNEP25.TFI.html"), 200)],
    )
    assert len(rows) == 50
    assert isinstance(rows[0], BiznesRadarEquityHistoricalData)
    assert rows[0].date == date(2026, 9, 11)
    assert rows[0].close == 14.66
    for row in rows:
        assert row.volume == 0
        assert row.open == row.high == row.low == row.close
    assert rows[1].close == 14.65


def test_fund_fetcher_range_filter(httpx_mock, read_fixture):
    rows = _fetch(
        httpx_mock,
        {"symbol": "NNEP25.TFI", "start_date": date(2026, 9, 9), "end_date": date(2026, 9, 11)},
        [(read_fixture("NNEP25.TFI.html"), 200)],
    )
    assert [r.date for r in rows] == [date(2026, 9, 11), date(2026, 9, 10), date(2026, 9, 9)]
    assert [r.close for r in rows] == [14.66, 14.65, 14.70]


def test_fund_fetcher_empty_result_in_range(httpx_mock, read_fixture):
    rows = _fetch(
        httpx_mock,
        {"symbol": "NNEP25.TFI", "start_date": date(2027, 1, 1), "end_date": date(2027, 12, 31)},
        [(read_fixture("NNEP25.TFI.html"), 200)],
    )
    assert rows == []


def test_fund_fetcher_default_bounds_when_dates_missing(httpx_mock, read_fixture):
    rows = _fetch(
        httpx_mock,
        {"symbol": "NNEP25.TFI"},
        [(read_fixture("NNEP25.TFI.html"), 200)],
    )
    assert len(rows) == 50  # no start/end → full available history


def test_parse_fund_row_maps_to_ohlcv():
    row = parse_fund_row({"date": date(2026, 9, 11), "close": 14.66})
    assert row == {
        "date": date(2026, 9, 11),
        "open": 14.66,
        "high": 14.66,
        "low": 14.66,
        "close": 14.66,
        "volume": 0,
    }


def test_transform_query_accepts_snake_and_camel_keys():
    params = {"symbol": "nNep25.tfi", "start_date": "2026-01-01", "end_date": "2026-06-30"}
    query = EquityHistoricalFetcher.transform_query(params)
    assert query.symbol == "NNEP25.TFI"  # upper-cased by the standard model
    assert query.start_date == date(2026, 1, 1)
    assert query.end_date == date(2026, 6, 30)
    query = EquityHistoricalFetcher.transform_query(
        {"symbol": "NNEP25.TFI", "startDate": "2026-01-01", "endDate": "2026-06-30"}
    )
    assert query.start_date == date(2026, 1, 1)