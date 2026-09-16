"""FixedIncomeHistorical fetcher stub tests (D79 19.5)."""

from datetime import date

from openbb_obligacje import obligacje_provider
from openbb_obligacje.models.fixedincome_historical import (
    FixedIncomeHistoricalFetcher,
    ObligacjeFixedIncomeHistoricalData,
    ObligacjeFixedIncomeHistoricalQueryParams,
)


def test_transform_query_defaults():
    q = FixedIncomeHistoricalFetcher.transform_query({"symbol": "EDO0936"})
    assert isinstance(q, ObligacjeFixedIncomeHistoricalQueryParams)
    assert q.symbol == "EDO0936"
    assert q.start_date is None
    assert q.end_date is None


def test_transform_query_camel_case_alias():
    q = FixedIncomeHistoricalFetcher.transform_query(
        {"symbol": "EDO0936", "startDate": "2026-09-01", "end_date": "2026-12-01"}
    )
    assert q.start_date == date(2026, 9, 1)
    assert q.end_date == date(2026, 12, 1)


def test_extract_data_stub_is_empty():
    q = FixedIncomeHistoricalFetcher.transform_query({"symbol": "EDO0936"})
    assert FixedIncomeHistoricalFetcher.extract_data(q) == []


def test_transform_data_round_trip():
    q = FixedIncomeHistoricalFetcher.transform_query({"symbol": "EDO0936"})
    rows = [
        {
            "date": "2014-05-10",
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 0,
        }
    ]
    out = FixedIncomeHistoricalFetcher.transform_data(q, rows)
    assert isinstance(out[0], ObligacjeFixedIncomeHistoricalData)
    assert out[0].close == 100.0
    assert out[0].date == date(2014, 5, 10)


def test_registered_under_fixedincome_historical():
    assert obligacje_provider.fetcher_dict["FixedIncomeHistorical"] is FixedIncomeHistoricalFetcher