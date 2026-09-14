"""EquityProfileFetcher tests (D78 17.4a) — minimal EquityInfo profile."""

from openbb_biznesradar.models import equity_profile

_PROBE_PAGE = (
    "<html><head><title>Notowania BST0327 BEST- BiznesRadar.pl</title></head>"
    "<body><table class='qTableFull contentList'><tr><th>x</th></tr></table></body></html>"
)


def test_extract_data_returns_profile_when_found(monkeypatch):
    monkeypatch.setattr(equity_profile, "probe_notowania", lambda sym: "BEST SA")
    query = equity_profile.EquityProfileFetcher.transform_query({"symbol": "BST0327.WA"})
    data = equity_profile.EquityProfileFetcher.extract_data(query)
    assert len(data) == 1
    assert data[0]["symbol"] == "BST0327.WA"
    assert data[0]["name"] == "BEST SA"
    assert data[0]["hq_country"] == "PL"
    assert data[0]["stock_exchange"] == "GPW"


def test_extract_data_returns_empty_when_not_found(monkeypatch):
    monkeypatch.setattr(equity_profile, "probe_notowania", lambda sym: None)
    query = equity_profile.EquityProfileFetcher.transform_query({"symbol": "ZZZZZZ"})
    assert equity_profile.EquityProfileFetcher.extract_data(query) == []


def test_transform_data_builds_standard_model(monkeypatch):
    monkeypatch.setattr(equity_profile, "probe_notowania", lambda sym: "BEST SA")
    query = equity_profile.EquityProfileFetcher.transform_query({"symbol": "BST0327.WA"})
    data = equity_profile.EquityProfileFetcher.extract_data(query)
    out = equity_profile.EquityProfileFetcher.transform_data(query, data)
    assert out[0].symbol == "BST0327.WA"
    assert out[0].name == "BEST SA"
    assert out[0].hq_country == "PL"


def test_registered_under_equity_info():
    from openbb_biznesradar import biznesradar_provider

    assert biznesradar_provider.fetcher_dict["EquityInfo"] is equity_profile.EquityProfileFetcher
