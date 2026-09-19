"""CorporateBondProfileFetcher tests (D80 25.2) — obligacje.pl profile scrape.

Pins the parser against the captured fixture
``tests/fixtures/obligacje_bond_profile_BST0327.html``.

Monkeypatching note: ``CorporateBondProfileFetcher.extract_data`` resolves
``scrape_bond_profile`` as ``obligacje.scrape_bond_profile`` (module-attribute
lookup at call time), so the dispatch tests patch
``openbb_biznesradar.obligacje.scrape_bond_profile``;
``EquityProfileFetcher.extract_data`` calls ``probe_notowania`` from its own
module namespace, so the biznesradar probe is patched on
``openbb_biznesradar.models.equity_profile``.
"""

import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from openbb_biznesradar import obligacje
from openbb_biznesradar.models import corp_bond_profile, equity_profile

PROFILE_FIXTURE = Path(__file__).parents[3] / "tests" / "fixtures" / (
    "obligacje_bond_profile_BST0327.html"
)


def _fixture_profile() -> dict:
    return obligacje.parse_bond_profile_html(
        PROFILE_FIXTURE.read_text(encoding="utf-8")
    )


# --- symbol pattern -----------------------------------------------------------


@pytest.mark.parametrize(
    "symbol",
    ["BST0327", "BST0327.WA", "BOS0735-K", "PKO1034-K", "bst0327", "  SIR0228 "],
)
def test_is_catalyst_bond_symbol_matches(symbol):
    assert obligacje.is_catalyst_bond_symbol(symbol) is True


@pytest.mark.parametrize(
    "symbol",
    ["AAPL", "NNEP25.TFI", "BTC-USD", "BST032", "BST03271"],
)
def test_is_catalyst_bond_symbol_rejects(symbol):
    assert obligacje.is_catalyst_bond_symbol(symbol) is False


def test_savings_bond_codes_match_pattern_but_are_not_bonds():
    """Pattern is ambiguous on purpose — dispatch resolves via the 404 fallback."""
    assert obligacje.is_catalyst_bond_symbol("ROD1033") is True
    assert obligacje.is_catalyst_bond_symbol("EDO0936") is True


# --- dispatch through fetch_data ---------------------------------------------


def test_dispatch_catalyst_symbol_to_corp_bond_fetcher(monkeypatch):
    """BST0327 returns the obligacje.pl corp-bond profile without a biznesradar probe."""
    called = {}
    monkeypatch.setattr(
        equity_profile,
        "probe_notowania",
        lambda s: called.setdefault("br", "MUST NOT BE CALLED"),
    )
    monkeypatch.setattr(
        obligacje,
        "scrape_bond_profile",
        lambda s: called.setdefault(
            "ob",
            {"symbol": s, "issuer": "X", "asset_type": "corp_bond", "country": "PL"},
        ),
    )
    result = asyncio.run(
        equity_profile.EquityProfileFetcher.fetch_data({"symbol": "BST0327.WA"})
    )
    assert "br" not in called, "biznesradar probe must not run for Catalyst bonds"
    assert called.get("ob") is not None
    assert isinstance(result, list) and len(result) == 1
    assert result[0].issuer == "X"
    assert result[0].asset_type == "corp_bond"
    assert result[0].symbol == "BST0327.WA"


def test_dispatch_non_bond_symbol_keeps_biznesradar(monkeypatch):
    called = {}
    monkeypatch.setattr(
        equity_profile, "probe_notowania", lambda s: called.setdefault("br", "BEST SA")
    )
    monkeypatch.setattr(
        obligacje,
        "scrape_bond_profile",
        lambda s: called.setdefault("ob", "MUST NOT BE CALLED"),
    )
    result = asyncio.run(
        equity_profile.EquityProfileFetcher.fetch_data({"symbol": "NNEP25.TFI"})
    )
    assert called.get("br") == "BEST SA"
    assert "ob" not in called, "obligacje.pl must not be scraped for funds"
    assert len(result) == 1
    assert result[0].name == "BEST SA"
    assert result[0].hq_country == "PL"


def test_dispatch_falls_back_to_biznesradar_when_bond_page_404s(monkeypatch):
    """Savings-bond-shaped codes (ROD1033/EDO0936) 404 on obligacje.pl -> biznesradar."""
    called = {}
    monkeypatch.setattr(
        obligacje,
        "scrape_bond_profile",
        lambda s: called.setdefault("ob", None),
    )
    monkeypatch.setattr(
        equity_profile, "probe_notowania", lambda s: called.setdefault("br", "NNEP25 FIO")
    )
    result = asyncio.run(
        equity_profile.EquityProfileFetcher.fetch_data({"symbol": "ROD1033"})
    )
    assert called.get("ob") is None
    assert called.get("br") == "NNEP25 FIO"
    assert len(result) == 1
    assert result[0].name == "NNEP25 FIO"


def test_dispatch_bond_page_error_falls_back_to_biznesradar(monkeypatch):
    """A bond-page crash degrades to the biznesradar path, never 500."""
    called = {}

    def boom(s):
        raise ConnectionError("network down")

    monkeypatch.setattr(obligacje, "scrape_bond_profile", boom)
    monkeypatch.setattr(
        equity_profile, "probe_notowania", lambda s: called.setdefault("br", "BEST SA")
    )
    result = asyncio.run(
        equity_profile.EquityProfileFetcher.fetch_data({"symbol": "BST0327"})
    )
    assert called.get("br") == "BEST SA"
    assert len(result) == 1
    assert result[0].name == "BEST SA"


# --- parser against the fixture ----------------------------------------------


def test_parse_fixture_full_profile():
    p = _fixture_profile()
    assert p is not None
    assert p["issuer"] == "Best S.A."
    assert p["series"] == "W3"
    assert p["isin"] == "PLBEST000333"
    assert p["market"] == "GPW RR"
    assert p["status"] == "Notowane"
    assert p["nominal_value"] == 100.0
    assert p["nominal_currency"] == "PLN"
    assert p["secured"] == "NIE"
    assert p["coupon_type"] == "zmienne WIBOR 3M + 4%"
    assert p["current_rate"] == "7.83%"
    assert p["maturity"] == "2027-03-07"
    assert p["asset_type"] == "corp_bond"
    assert p["country"] == "PL"
    assert p["currency"] == "PLN"
    assert p["margin"] is None


def test_parse_non_bond_page_returns_none():
    assert obligacje.parse_bond_profile_html(
        "<html><body><table class='qTableFull'><tr><td>x</td></tr></table></body></html>"
    ) is None


def test_scrape_bond_profile_strips_wa_and_404s(monkeypatch):
    import httpx

    seen = {}

    def fake_get(url, headers=None, timeout=None):
        seen["url"] = url

        class R:
            status_code = 404
            text = ""

        return R()

    monkeypatch.setattr(httpx, "get", fake_get)
    assert obligacje.scrape_bond_profile("BST0327.WA") is None
    assert seen["url"] == "https://obligacje.pl/pl/obligacja/BST0327"


def test_scrape_bond_profile_parses_response(monkeypatch):
    import httpx

    html = PROFILE_FIXTURE.read_text(encoding="utf-8")

    class R:
        status_code = 200
        text = html

    monkeypatch.setattr(httpx, "get", lambda url, headers=None, timeout=None: R())
    profile = obligacje.scrape_bond_profile("bst0327")
    assert profile is not None
    assert profile["symbol"] == "bst0327"
    assert profile["issuer"] == "Best S.A."


def test_extract_and_transform_data(monkeypatch):
    profile = _fixture_profile()
    # scrape_bond_profile (the real extract path) attaches the symbol key
    profile["symbol"] = "BST0327"
    monkeypatch.setattr(obligacje, "scrape_bond_profile", lambda s: profile)
    query = corp_bond_profile.CorporateBondProfileFetcher.transform_query(
        {"symbol": "BST0327"}
    )
    rows = corp_bond_profile.CorporateBondProfileFetcher.extract_data(query)
    assert len(rows) == 1
    out = corp_bond_profile.CorporateBondProfileFetcher.transform_data(query, rows)
    assert out[0].symbol == "BST0327"
    assert out[0].name == "Best S.A."
    assert out[0].isin == "PLBEST000333"
    assert out[0].stock_exchange == "GPW RR"
    assert out[0].hq_country == "PL"
    assert out[0].asset_type == "corp_bond"
    assert out[0].issuer == "Best S.A."
    assert out[0].market == "GPW RR"
    assert out[0].nominal_value == Decimal("100.00")
    assert out[0].coupon_type == "zmienne WIBOR 3M + 4%"
    assert out[0].maturity_date == date(2027, 3, 7)
    assert out[0].currency == "PLN"


def test_extract_data_empty_when_unknown(monkeypatch):
    monkeypatch.setattr(obligacje, "scrape_bond_profile", lambda s: None)
    query = corp_bond_profile.CorporateBondProfileFetcher.transform_query(
        {"symbol": "BST9999"}
    )
    assert corp_bond_profile.CorporateBondProfileFetcher.extract_data(query) == []
