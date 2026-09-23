"""dividendmax HistoricalDividendsFetcher tests (plan §52.4)."""

from datetime import date

import pytest

from openbb_dividendmax import client
from openbb_dividendmax.models.historical_dividends import (
    DividendmaxHistoricalDividendsData,
    HistoricalDividendsFetcher,
)


def test_transform_query_maps_fields():
    query = HistoricalDividendsFetcher.transform_query({"symbol": "AAPL"})
    assert query.symbol == "AAPL"
    assert query.start_date is None
    assert query.end_date is None


def test_extract_data_scrapes_history(monkeypatch):
    seen = {}

    def fake_scrape(symbol, fetch_delay_s=None):
        seen["symbol"] = symbol
        return [
            {
                "symbol": symbol,
                "ex_dividend_date": date(2026, 8, 10),
                "payment_date": date(2026, 8, 13),
                "declaration_date": date(2026, 7, 30),
                "amount": 0.27,
                "currency": "USD",
                "dividend_type": "Quarterly",
                "status": "Paid",
            }
        ]

    monkeypatch.setattr(client, "scrape_dividend_history", fake_scrape)
    # The fetcher imports the function directly; patch at its import site too.
    import openbb_dividendmax.models.historical_dividends as hd

    monkeypatch.setattr(hd, "scrape_dividend_history", fake_scrape)
    query = HistoricalDividendsFetcher.transform_query({"symbol": "AAPL"})
    data = HistoricalDividendsFetcher.extract_data(query)
    assert seen["symbol"] == "AAPL"
    assert len(data) == 1
    assert data[0]["amount"] == 0.27


def test_extract_data_unknown_symbol_empty(monkeypatch):
    import openbb_dividendmax.models.historical_dividends as hd

    monkeypatch.setattr(hd, "scrape_dividend_history", lambda symbol, fetch_delay_s=None: [])
    query = HistoricalDividendsFetcher.transform_query({"symbol": "ZZZZZ"})
    assert HistoricalDividendsFetcher.extract_data(query) == []


def test_transform_data_builds_standard_model():
    query = HistoricalDividendsFetcher.transform_query({"symbol": "AAPL"})
    data = [
        {
            "symbol": "AAPL",
            "ex_dividend_date": date(2026, 8, 10),
            "payment_date": date(2026, 8, 13),
            "declaration_date": date(2026, 7, 30),
            "amount": 0.27,
            "currency": "USD",
            "dividend_type": "Quarterly",
            "status": "Paid",
        }
    ]
    out = HistoricalDividendsFetcher.transform_data(query, data)
    assert isinstance(out[0], DividendmaxHistoricalDividendsData)
    assert out[0].symbol == "AAPL"
    assert out[0].ex_dividend_date == date(2026, 8, 10)
    assert out[0].amount == 0.27
    assert out[0].payment_date == date(2026, 8, 13)
    assert out[0].declaration_date == date(2026, 7, 30)
    assert out[0].currency == "USD"
    assert out[0].dividend_type == "Quarterly"
    assert out[0].status == "Paid"


def test_registered_under_historical_dividends():
    from openbb_dividendmax import dividendmax_provider

    assert (
        dividendmax_provider.fetcher_dict["HistoricalDividends"] is HistoricalDividendsFetcher
    )
    assert "CalendarDividend" not in dividendmax_provider.fetcher_dict
