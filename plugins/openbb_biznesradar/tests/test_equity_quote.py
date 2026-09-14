"""EquityQuoteFetcher tests (D78 17.3) — /notowania/{symbol} quote scrape."""

from openbb_biznesradar import scraper
from openbb_biznesradar.models import equity_quote

# ---------------------------------------------------------------------------
# Minimal HTML helpers
# ---------------------------------------------------------------------------

_BOND_QUOTE_PAGE = """\
<html>
<head><title>Notowania BST0327 BEST- BiznesRadar.pl</title></head>
<body>
<table class='qTableFull contentList'><tr><th>stopa zwrotu</th></tr></table>
<table>
  <tr class="current">
    <th><strong>Kurs</strong>:</th>
    <td id="pr_t_close"><span class="q_ch_act">101.30</span></td>
  </tr>
  <tr class="current compare_past">
    <th>Zmiana 1d:</th>
    <td><span class="q_ch_pkt cplus">+0.30</span></td>
    <td><span class="q_ch_per cplus">(+0.30%)</span></td>
    <td class="compare_base_value"><span class="q_ch_prev">101.00</span></td>
    <td>09.09.2026</td>
  </tr>
  <tr><td id="pr_t_date">10 wrz 16:30</td></tr>
  <tr><td id="pr_t_open">101.30</td></tr>
  <tr><td id="pr_t_max">101.30</td></tr>
  <tr><td id="pr_t_min">101.30</td></tr>
  <tr><td id="pr_t_vol">60</td></tr>
</table>
</body>
</html>
"""

_FUND_QUOTE_PAGE = """\
<html>
<head><title>Notowania ING Emerytura 2025 (ING Emerytura SFIO)- BiznesRadar.pl</title></head>
<body>
<table class='qTableFull contentList'><tr><th>stopa zwrotu</th></tr></table>
<table>
  <tr class="current">
    <th><strong>Kurs</strong>:</th>
    <td id="pr_t_close"><span class="q_ch_act">14.66</span></td>
  </tr>
  <tr class="current compare_past">
    <th>Zmiana 1d:</th>
    <td><span class="q_ch_pkt cplus">+0.01</span></td>
    <td><span class="q_ch_per cplus">(+0.07%)</span></td>
    <td class="compare_base_value"><span class="q_ch_prev">14.65</span></td>
    <td>10.09.2026</td>
  </tr>
  <tr><td id="pr_t_open">14.66</td></tr>
  <tr><td id="pr_t_max">14.66</td></tr>
  <tr><td id="pr_t_min">14.66</td></tr>
</table>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# scraper.scrape_quote
# ---------------------------------------------------------------------------


def test_scrape_quote_bond(httpx_mock):
    httpx_mock([(_BOND_QUOTE_PAGE, 200)])
    result = scraper.scrape_quote("BST0327.WA")
    assert result is not None
    assert result["symbol"] == "BST0327.WA"
    assert result["name"] == "BST0327 BEST"
    assert result["last_price"] == 101.30
    assert result["open"] == 101.30
    assert result["high"] == 101.30
    assert result["low"] == 101.30
    assert result["volume"] == 60
    assert result["change"] == pytest.approx(0.30)
    assert result["change_percent"] == pytest.approx(0.0030)
    assert result["prev_close"] == 101.00


def test_scrape_quote_fund(httpx_mock):
    httpx_mock([(_FUND_QUOTE_PAGE, 200)])
    result = scraper.scrape_quote("NNEP25.TFI")
    assert result is not None
    assert result["name"] == "ING Emerytura 2025 (ING Emerytura SFIO)"
    assert result["last_price"] == 14.66
    assert result["change"] == pytest.approx(0.01)
    assert result["change_percent"] == pytest.approx(0.0007)
    assert result["prev_close"] == 14.65
    assert result["volume"] is None  # fund page has no volume


def test_scrape_quote_strips_wa_for_url(httpx_mock):
    calls = httpx_mock([(_BOND_QUOTE_PAGE, 200)])
    scraper.scrape_quote("BST0327.WA")
    assert calls == ["https://www.biznesradar.pl/notowania/BST0327"]


def test_scrape_quote_404_returns_none(httpx_mock):
    httpx_mock([("", 404)])
    assert scraper.scrape_quote("ZZZZZZ") is None


def test_scrape_quote_no_table_returns_none(httpx_mock):
    httpx_mock([("<html><body><p>not an instrument</p></body></html>", 200)])
    assert scraper.scrape_quote("ZZZZZZ") is None


# ---------------------------------------------------------------------------
# EquityQuoteFetcher
# ---------------------------------------------------------------------------


def test_extract_data_returns_single_row(monkeypatch):
    monkeypatch.setattr(
        equity_quote,
        "scrape_quote",
        lambda sym: {
            "symbol": sym,
            "name": "BEST",
            "last_price": 101.30,
            "open": 101.30,
            "high": 101.30,
            "low": 101.30,
            "volume": 60,
            "change": 0.30,
            "change_percent": 0.003,
            "prev_close": 101.00,
        },
    )
    query = equity_quote.EquityQuoteFetcher.transform_query({"symbol": "BST0327.WA"})
    data = equity_quote.EquityQuoteFetcher.extract_data(query)
    assert len(data) == 1
    assert data[0]["symbol"] == "BST0327.WA"
    assert data[0]["last_price"] == 101.30


def test_extract_data_not_found_returns_empty(monkeypatch):
    monkeypatch.setattr(equity_quote, "scrape_quote", lambda sym: None)
    query = equity_quote.EquityQuoteFetcher.transform_query({"symbol": "ZZZZZZ"})
    assert equity_quote.EquityQuoteFetcher.extract_data(query) == []


def test_transform_data_builds_standard_model(monkeypatch):
    monkeypatch.setattr(
        equity_quote,
        "scrape_quote",
        lambda sym: {
            "symbol": sym,
            "name": "BEST",
            "last_price": 101.30,
            "open": None,
            "high": None,
            "low": None,
            "volume": None,
            "change": None,
            "change_percent": None,
            "prev_close": None,
        },
    )
    query = equity_quote.EquityQuoteFetcher.transform_query({"symbol": "BST0327.WA"})
    data = equity_quote.EquityQuoteFetcher.extract_data(query)
    out = equity_quote.EquityQuoteFetcher.transform_data(query, data)
    assert out[0].symbol == "BST0327.WA"
    assert out[0].name == "BEST"
    assert out[0].last_price == 101.30


def test_registered_under_equity_quote():
    from openbb_biznesradar import biznesradar_provider

    assert biznesradar_provider.fetcher_dict["EquityQuote"] is equity_quote.EquityQuoteFetcher


import pytest
