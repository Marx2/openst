"""EquityHistoricalFetcher dispatch tests (D77 16.4) — fund vs bond by symbol shape."""

from datetime import date

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