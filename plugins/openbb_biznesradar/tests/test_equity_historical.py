"""EquityHistoricalFetcher dispatch tests (D77 16.4) — fund vs bond by symbol shape."""

from datetime import date

import pytest

from openbb_biznesradar.models import equity_historical
from openbb_biznesradar.models.bond_historical import BOND_COLUMNS
from openbb_biznesradar.models.fund_historical import FUND_COLUMNS


def test_is_fund_by_venue_suffix():
    assert equity_historical._is_fund("NNEP25.TFI")
    assert equity_historical._is_fund("XYZ.FIZ")
    assert equity_historical._is_fund("nNep25.TFI")  # case-insensitive
    assert not equity_historical._is_fund("BST0327")
    assert not equity_historical._is_fund("XTB.WA")


def test_dispatch_selects_fund_columns():
    assert equity_historical._is_fund("NNEP25.TFI") and FUND_COLUMNS == {"date": 0, "close": 1}
    assert not equity_historical._is_fund("BST0327") and BOND_COLUMNS == {
        "date": 0,
        "open": 1,
        "high": 2,
        "low": 3,
        "close": 4,
        "volume": 5,
    }


def test_extract_data_passes_default_bounds(monkeypatch):
    """Without start/end the fetcher must use an empty-wide range, not crash."""
    seen = {}

    def fake_scrape(symbol, start_date, end_date, delay, cols):
        seen["symbol"] = symbol
        seen["start_date"] = start_date
        seen["end_date"] = end_date
        seen["cols"] = cols
        return iter([])

    monkeypatch.setattr(equity_historical, "_scrape_pages", fake_scrape)
    query = equity_historical.EquityHistoricalFetcher.transform_query({"symbol": "BST0327"})
    result = equity_historical.EquityHistoricalFetcher.extract_data(query)
    assert result == []
    assert seen["symbol"] == "BST0327"
    assert seen["start_date"] == date(1900, 1, 1)
    assert seen["end_date"] == date(9999, 12, 31)
    assert seen["cols"] is BOND_COLUMNS


def test_extract_data_dispatches_to_fund_columns(monkeypatch):
    seen = {}

    def fake_scrape(symbol, start_date, end_date, delay, cols):
        seen["cols"] = cols
        return iter([])

    monkeypatch.setattr(equity_historical, "_scrape_pages", fake_scrape)
    query = equity_historical.EquityHistoricalFetcher.transform_query(
        {"symbol": "NNEP25.TFI", "start_date": date(2026, 1, 1), "end_date": date(2026, 6, 30)}
    )
    equity_historical.EquityHistoricalFetcher.extract_data(query)
    assert seen["cols"] is FUND_COLUMNS

def test_fetch_delay_fund_lower_than_bond(monkeypatch):
    """plan §45.5 — funds use a lower per-page delay so an 11-yr window sits
    under the 60 s ingress cap; bonds keep the polite 2.0 s default."""
    monkeypatch.delenv("BIZNESRADAR_FETCH_DELAY_S", raising=False)
    monkeypatch.delenv("BIZNESRADAR_FUND_FETCH_DELAY_S", raising=False)
    assert equity_historical._fetch_delay_s(is_fund=True) == pytest.approx(0.3)
    assert equity_historical._fetch_delay_s(is_fund=False) == pytest.approx(2.0)
    # default (no arg) stays the bond delay for backwards compat
    assert equity_historical._fetch_delay_s() == pytest.approx(2.0)


def test_fetch_delay_fund_overridable(monkeypatch):
    monkeypatch.setenv("BIZNESRADAR_FUND_FETCH_DELAY_S", "0.1")
    assert equity_historical._fetch_delay_s(is_fund=True) == pytest.approx(0.1)


def test_extract_data_uses_fund_delay(monkeypatch):
    seen = {}
    monkeypatch.delenv("BIZNESRADAR_FUND_FETCH_DELAY_S", raising=False)

    def fake_scrape(symbol, start_date, end_date, delay, cols):
        seen["delay"] = delay
        return iter([])

    monkeypatch.setattr(equity_historical, "_scrape_pages", fake_scrape)
    query = equity_historical.EquityHistoricalFetcher.transform_query(
        {"symbol": "NNEP25.TFI", "start_date": date(2020, 1, 1), "end_date": date(2026, 6, 30)}
    )
    equity_historical.EquityHistoricalFetcher.extract_data(query)
    assert seen["delay"] == pytest.approx(0.3)


def test_extract_data_uses_bond_delay(monkeypatch):
    seen = {}
    monkeypatch.delenv("BIZNESRADAR_FETCH_DELAY_S", raising=False)

    def fake_scrape(symbol, start_date, end_date, delay, cols):
        seen["delay"] = delay
        return iter([])

    monkeypatch.setattr(equity_historical, "_scrape_pages", fake_scrape)
    query = equity_historical.EquityHistoricalFetcher.transform_query(
        {"symbol": "BST0327", "start_date": date(2020, 1, 1), "end_date": date(2026, 6, 30)}
    )
    equity_historical.EquityHistoricalFetcher.extract_data(query)
    assert seen["delay"] == pytest.approx(2.0)
