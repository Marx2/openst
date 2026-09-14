"""EquitySearchFetcher probe tests (D78 17.1) — /notowania/{symbol} probe."""

from openbb_biznesradar import scraper
from openbb_biznesradar.models import equity_search

QUOTE_PAGE = (
    "<html><head><title>Notowania BST0327 BEST- BiznesRadar.pl</title></head>"
    "<body><table class='qTableFull contentList'><tr><th>stopa zwrotu</th></tr></table></body></html>"
)


def _page(title: str) -> str:
    return (
        f"<html><head><title>{title}</title></head>"
        "<body><table class='qTableFull contentList'><tr><th>x</th></tr></table></body></html>"
    )


# ---------------------------------------------------------------------------
# scraper.probe_notowania
# ---------------------------------------------------------------------------


def test_probe_hit_extracts_name_from_title(httpx_mock):
    calls = httpx_mock([(QUOTE_PAGE, 200)])
    assert scraper.probe_notowania("BST0327") == "BST0327 BEST"
    assert calls == ["https://www.biznesradar.pl/notowania/BST0327"]


def test_probe_strips_wa_suffix_for_url(httpx_mock):
    calls = httpx_mock([(QUOTE_PAGE, 200)])
    assert scraper.probe_notowania("BST0327.WA") == "BST0327 BEST"
    assert calls == ["https://www.biznesradar.pl/notowania/BST0327"]


def test_probe_fund_title_without_symbol(httpx_mock):
    html = _page("Notowania ING Emerytura 2025 (ING Emerytura SFIO)- BiznesRadar.pl")
    httpx_mock([(html, 200)])
    assert scraper.probe_notowania("NNEP25.TFI") == "ING Emerytura 2025 (ING Emerytura SFIO)"


def test_probe_404_returns_none(httpx_mock):
    httpx_mock([("", 404)])
    assert scraper.probe_notowania("ZZZZZ") is None


def test_probe_missing_quote_table_returns_none(httpx_mock):
    httpx_mock([("<html><body>not an instrument page</body></html>", 200)])
    assert scraper.probe_notowania("BST0327") is None


def test_probe_falls_back_to_h2(httpx_mock):
    html = "<html><head><title>Notowania  - BiznesRadar.pl</title></head>"
    html += "<body><h2>BEST SA</h2><table class='qTableFull'><tr><th>x</th></tr></table></body></html>"
    httpx_mock([(html, 200)])
    assert scraper.probe_notowania("BST0327") == "BEST SA"


# ---------------------------------------------------------------------------
# EquitySearchFetcher
# ---------------------------------------------------------------------------


def test_extract_data_normalizes_symbol_keeping_suffix(monkeypatch):
    seen = {}

    def fake_probe(symbol):
        seen["symbol"] = symbol
        return "BEST"

    monkeypatch.setattr(equity_search, "probe_notowania", fake_probe)
    query = equity_search.EquitySearchFetcher.transform_query({"query": " bst0327.wa "})
    result = equity_search.EquitySearchFetcher.extract_data(query)
    assert result == [{"name": "BEST", "symbol": "BST0327.WA", "cik": None}]
    assert seen["symbol"] == "BST0327.WA"


def test_extract_data_empty_query_returns_empty():
    query = equity_search.EquitySearchFetcher.transform_query({"query": ""})
    assert equity_search.EquitySearchFetcher.extract_data(query) == []


def test_extract_data_no_hit_returns_empty(monkeypatch):
    monkeypatch.setattr(equity_search, "probe_notowania", lambda symbol: None)
    query = equity_search.EquitySearchFetcher.transform_query({"query": "XYZ"})
    assert equity_search.EquitySearchFetcher.extract_data(query) == []


def test_transform_data_builds_standard_model():
    query = equity_search.EquitySearchFetcher.transform_query({"query": "BST0327.WA"})
    data = [{"name": "BEST", "symbol": "BST0327.WA", "cik": None}]
    out = equity_search.EquitySearchFetcher.transform_data(query, data)
    assert out[0].symbol == "BST0327.WA"
    assert out[0].name == "BEST"
    assert out[0].cik is None


# ---------------------------------------------------------------------------
# provider registration
# ---------------------------------------------------------------------------


def test_registered_under_equity_search():
    from openbb_biznesradar import biznesradar_provider

    assert biznesradar_provider.fetcher_dict["EquitySearch"] is equity_search.EquitySearchFetcher