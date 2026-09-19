import json
import logging
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import src.cache as cache_module


@pytest.fixture(autouse=True)
def flush_redis():
    c = cache_module.RedisCache(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        password=os.environ.get("REDIS_PASSWORD") or None,
        db=int(os.environ.get("REDIS_DB", 0)),
    )
    c._client.flushdb()
    yield
    c._client.flushdb()


@pytest.fixture
def client():
    from src.main import app
    return TestClient(app)


@patch("src.main.get_dividend_yield", return_value=2.45)
def test_yield_miss_fetches_and_returns(mock_fn, client):
    r = client.get("/dividend/yield/AAPL")
    assert r.status_code == 200
    assert r.json() == 2.45
    mock_fn.assert_called_once_with("AAPL")


@patch("src.main.get_dividend_yield", return_value=2.45)
def test_yield_hit_returns_cached(mock_fn, client):
    client.get("/dividend/yield/AAPL")
    client.get("/dividend/yield/AAPL")
    assert mock_fn.call_count == 1


@patch("src.main.get_dividend_yield", return_value=None)
def test_yield_not_found_returns_404(mock_fn, client):
    r = client.get("/dividend/yield/UNKNOWN")
    assert r.status_code == 404


@patch("src.main.get_dividend_history", return_value=[{"date": "2024-03-15", "amount": "0.2500"}])
def test_history_miss_fetches_and_returns(mock_fn, client):
    r = client.get("/dividend/history/AAPL")
    assert r.status_code == 200
    assert r.json() == [{"date": "2024-03-15", "amount": "0.2500"}]
    mock_fn.assert_called_once_with("AAPL")


@patch("src.main.get_dividend_history", return_value=[{"date": "2024-03-15", "amount": "0.2500"}])
def test_history_hit_returns_cached(mock_fn, client):
    client.get("/dividend/history/AAPL")
    client.get("/dividend/history/AAPL")
    assert mock_fn.call_count == 1


@patch("src.main.get_dividend_history", return_value=None)
def test_history_not_found_returns_404(mock_fn, client):
    r = client.get("/dividend/history/UNKNOWN")
    assert r.status_code == 404


@patch("src.main.get_price_history", return_value=[{"date": "2025-08-01", "close": 195.5}])
def test_price_history_miss_fetches_and_returns(mock_fn, client):
    r = client.get("/price/history/AAPL")
    assert r.status_code == 200
    assert r.json() == [{"date": "2025-08-01", "close": 195.5}]
    mock_fn.assert_called_once()


@patch("src.main.get_price_history", return_value=[{"date": "2025-08-01", "close": 195.5}])
def test_price_history_hit_returns_cached(mock_fn, client):
    client.get("/price/history/AAPL")
    client.get("/price/history/AAPL")
    assert mock_fn.call_count == 1


@patch("src.main.get_price_history", return_value=None)
def test_price_history_not_found_returns_404(mock_fn, client):
    r = client.get("/price/history/UNKNOWN")
    assert r.status_code == 404


@patch("src.main.get_dividend_yield", return_value=2.45)
def test_middleware_logs_structured_json(mock_fn, client, caplog):
    with caplog.at_level(logging.INFO, logger="openst"):
        r = client.get("/dividend/yield/AAPL")
    assert r.status_code == 200
    records = [rec for rec in caplog.records if rec.name == "openst"]
    assert records
    rec = records[-1]
    assert rec.getMessage() == "http_request"
    assert rec.method == "GET"
    assert rec.path == "/dividend/yield/AAPL"
    assert rec.status_code == 200
    assert isinstance(rec.duration_ms, float)


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_metrics_returns_prometheus_text(client):
    client.get("/health")  # ensure an instrumented request is recorded
    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "http_server_request_duration" in r.text


# ---------------------------------------------------------------------------
# New instruments-surface routes
# ---------------------------------------------------------------------------


@patch("src.main.get_profile", return_value={"name": "Apple Inc"})
def test_profile_miss_fetches_and_returns(mock_fn, client):
    r = client.get("/equity/profile/AAPL")
    assert r.status_code == 200
    assert r.json() == {"name": "Apple Inc"}
    mock_fn.assert_called_once_with("AAPL")


@patch("src.main.get_profile", return_value=None)
def test_profile_not_found_returns_404(mock_fn, client):
    assert client.get("/equity/profile/UNKNOWN").status_code == 404


@patch("src.main.get_profile", return_value={"name": "Apple Inc"})
def test_profile_hit_returns_cached(mock_fn, client):
    client.get("/equity/profile/AAPL")
    client.get("/equity/profile/AAPL")
    assert mock_fn.call_count == 1


@patch("src.main.get_quote", return_value={"last_price": 232.14})
def test_quote_returns_record(mock_fn, client):
    r = client.get("/equity/quote/AAPL")
    assert r.status_code == 200
    assert r.json() == {"last_price": 232.14}


@patch("src.main.get_metrics", return_value={"market_cap": 3.1e12})
def test_metrics_returns_record(mock_fn, client):
    r = client.get("/equity/metrics/AAPL")
    assert r.status_code == 200
    assert r.json() == {"market_cap": 3.1e12}


@patch("src.main.get_projections", return_value={"target_median": 250.0})
def test_projections_returns_record(mock_fn, client):
    r = client.get("/equity/projections/AAPL")
    assert r.status_code == 200
    assert r.json() == {"target_median": 250.0}


@patch(
    "src.main.get_ohlcv_history",
    return_value=[{"date": "2025-08-01", "open": 194.0, "high": 196.2, "low": 193.5, "close": 195.5, "volume": 52301400}],
)
def test_price_ohlcv_defaults_to_one_year_window(mock_fn, client):
    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=365)

    r = client.get("/price/ohlcv/AAPL")
    assert r.status_code == 200
    assert len(r.json()) == 1
    mock_fn.assert_called_once_with("AAPL", str(start), str(end))


@patch("src.main.get_ohlcv_history", return_value=[])
def test_price_ohlcv_explicit_window_and_invalid_ticker_empty_list(mock_fn, client):
    r = client.get("/price/ohlcv/FAKE?start=2025-01-01&end=2025-02-01")
    assert r.status_code == 200
    assert r.json() == []
    mock_fn.assert_called_once_with("FAKE", "2025-01-01", "2025-02-01")


def test_price_ohlcv_rejects_bad_date_format(client):
    assert client.get("/price/ohlcv/AAPL?start=nope").status_code == 422


@patch(
    "src.main.get_crypto_ohlcv",
    return_value=[{"date": "2026-06-01", "open": 40000.0, "high": 40800.0, "low": 39600.0, "close": 40500.0, "volume": 900}],
)
def test_crypto_ohlcv_defaults_to_default_window(mock_fn, client):
    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=365)

    r = client.get("/crypto/ohlcv/BTC-USD")
    assert r.status_code == 200
    assert len(r.json()) == 1
    mock_fn.assert_called_once_with("BTC-USD", str(start), str(end))


@patch(
    "src.main.get_crypto_ohlcv",
    return_value=[{"date": "2026-06-01", "open": 40000.0, "high": 40800.0, "low": 39600.0, "close": 40500.0, "volume": 900}],
)
def test_crypto_ohlcv_explicit_window_forwarded(mock_fn, client):
    r = client.get("/crypto/ohlcv/BTC-USD?start=2026-01-01&end=2026-06-30")
    assert r.status_code == 200
    mock_fn.assert_called_once_with("BTC-USD", "2026-01-01", "2026-06-30")


@patch("src.main.get_crypto_ohlcv", return_value=None)
def test_crypto_ohlcv_not_found_returns_404(mock_fn, client):
    r = client.get("/crypto/ohlcv/FAKE-USD")
    assert r.status_code == 404


def test_crypto_ohlcv_rejects_bad_date_format(client):
    assert client.get("/crypto/ohlcv/BTC-USD?start=nope").status_code == 422


@patch("src.main.get_crypto_quote", return_value={"symbol": "ETH-USD", "price": 40500.0, "date": "2026-06-01"})
def test_crypto_quote_returns_json_body(mock_fn, client):
    r = client.get("/crypto/quote/ETH-USD")
    assert r.status_code == 200
    assert r.json() == {"symbol": "ETH-USD", "price": 40500.0, "date": "2026-06-01"}
    mock_fn.assert_called_once_with("ETH-USD")


@patch("src.main.get_crypto_quote", return_value=None)
def test_crypto_quote_not_found_returns_404(mock_fn, client):
    r = client.get("/crypto/quote/FAKE-USD")
    assert r.status_code == 404


@patch("src.main.get_crypto_search", return_value=[{"symbol": "BTC-USD", "name": "Bitcoin USD"}])
def test_crypto_search_normalizes_and_returns(mock_fn, client):
    r = client.get("/crypto/search/%20BTC%20")
    assert r.status_code == 200
    assert r.json()[0]["symbol"] == "BTC-USD"
    mock_fn.assert_called_once_with("btc")


@patch("src.main.get_crypto_search", return_value=[])
def test_crypto_search_empty_returns_404(mock_fn, client):
    assert client.get("/crypto/search/unknown").status_code == 404


@patch("src.main.get_crypto_profile", return_value={"symbol": "BTC-USD", "name": None, "currency": "USD"})
def test_crypto_profile_returns_json(mock_fn, client):
    r = client.get("/crypto/profile/BTC-USD")
    assert r.status_code == 200
    assert r.json() == {"symbol": "BTC-USD", "name": None, "currency": "USD"}
    mock_fn.assert_called_once_with("BTC-USD")


@patch("src.main.get_crypto_profile", return_value=None)
def test_crypto_profile_not_found_returns_404(mock_fn, client):
    assert client.get("/crypto/profile/FAKE-USD").status_code == 404


@patch(
    "src.main.get_fundamentals",
    return_value=[{"fiscal_year": 2024, "net_income": 93736}],
)
def test_fundamentals_defaults_income_annual(mock_fn, client):
    r = client.get("/equity/fundamentals/AAPL")
    assert r.status_code == 200
    assert r.json() == [{"fiscal_year": 2024, "net_income": 93736}]
    mock_fn.assert_called_once_with("AAPL", "income", "annual")


@patch("src.main.get_fundamentals", return_value=[{"fiscal_year": 2024}])
def test_fundamentals_statement_and_period_params(mock_fn, client):
    client.get("/equity/fundamentals/AAPL?statement=cash&period=quarter")
    mock_fn.assert_called_once_with("AAPL", "cash", "quarter")


def test_fundamentals_rejects_unknown_statement(client):
    assert client.get("/equity/fundamentals/AAPL?statement=hogwarts").status_code == 422


@patch("src.main.get_fundamentals", return_value=[])
def test_fundamentals_no_data_returns_404(mock_fn, client):
    assert client.get("/equity/fundamentals/UNKNOWN").status_code == 404


@patch(
    "src.main.get_calendar",
    return_value=[{"symbol": "AAPL", "eps_actual": 1.57}],
)
def test_calendar_earnings_window(mock_fn, client):
    r = client.get("/equity/calendar/earnings?start=2026-08-20&end=2026-08-25")
    assert r.status_code == 200
    assert r.json() == [{"symbol": "AAPL", "eps_actual": 1.57}]
    mock_fn.assert_called_once_with("earnings", "2026-08-20", "2026-08-25")


def test_calendar_unknown_kind_returns_404(client):
    assert client.get("/equity/calendar/hogwarts").status_code == 404


@patch("src.main.search_equities", return_value=[{"cik": 320193, "name": "Apple Inc", "symbol": "AAPL"}])
def test_search_normalizes_and_returns(mock_fn, client):
    r = client.get("/equity/search/%20Apple%20")
    assert r.status_code == 200
    assert r.json()[0]["symbol"] == "AAPL"
    mock_fn.assert_called_once_with("apple")


@patch("src.main.search_equities", return_value=[])
def test_search_no_results_404(mock_fn, client):
    assert client.get("/equity/search/zzzznope").status_code == 404


def test_meta_reports_service_and_version(client):
    r = client.get("/__meta")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "openst"
    assert body["impl"] == "real"
    assert isinstance(body["version"], str)


# ---------------------------------------------------------------------------
# SEC routes — insider trading / institutional ownership / filings / MD&A
# ---------------------------------------------------------------------------


@patch("src.main.get_insider_trading", return_value=[{"insider_name": "Tim Cook", "transaction_type": "P"}])
def test_ownership_miss_fetches_and_returns(mock_fn, client):
    r = client.get("/equity/ownership/AAPL")
    assert r.status_code == 200
    assert r.json() == [{"insider_name": "Tim Cook", "transaction_type": "P"}]
    mock_fn.assert_called_once_with("AAPL")


@patch("src.main.get_insider_trading", return_value=None)
def test_ownership_not_found_returns_404(mock_fn, client):
    assert client.get("/equity/ownership/UNKNOWN").status_code == 404


@patch("src.main.get_insider_trading", return_value=[{"insider_name": "Tim Cook"}])
def test_ownership_hit_returns_cached(mock_fn, client):
    client.get("/equity/ownership/AAPL")
    client.get("/equity/ownership/AAPL")
    assert mock_fn.call_count == 1


@patch("src.main.get_institutional_ownership", return_value=[{"fund_name": "Vanguard Group", "total_shares": 1000000}])
def test_institutional_ownership_returns_records(mock_fn, client):
    r = client.get("/equity/ownership/institutional/AAPL")
    assert r.status_code == 200
    assert r.json() == [{"fund_name": "Vanguard Group", "total_shares": 1000000}]
    mock_fn.assert_called_once_with("AAPL")


@patch("src.main.get_institutional_ownership", return_value=None)
def test_institutional_ownership_not_found_returns_404(mock_fn, client):
    assert client.get("/equity/ownership/institutional/UNKNOWN").status_code == 404


@patch("src.main.get_filings", return_value=[{"form_type": "10-K", "filing_date": "2026-08-21"}])
def test_filings_returns_records(mock_fn, client):
    r = client.get("/equity/filings/AAPL")
    assert r.status_code == 200
    assert r.json() == [{"form_type": "10-K", "filing_date": "2026-08-21"}]
    mock_fn.assert_called_once_with("AAPL")


@patch("src.main.get_filings", return_value=None)
def test_filings_not_found_returns_404(mock_fn, client):
    assert client.get("/equity/filings/UNKNOWN").status_code == 404


@patch("src.main.get_mda", return_value={"period": "FY2025", "content": "Results of Operations..."})
def test_mda_returns_record(mock_fn, client):
    r = client.get("/equity/fundamentals/AAPL/mda")
    assert r.status_code == 200
    assert r.json()["period"] == "FY2025"
    mock_fn.assert_called_once_with("AAPL")


@patch("src.main.get_mda", return_value=None)
def test_mda_not_found_returns_404(mock_fn, client):
    assert client.get("/equity/fundamentals/UNKNOWN/mda").status_code == 404


# ---------------------------------------------------------------------------
# News routes — /news/company/{ticker}
# ---------------------------------------------------------------------------


@patch(
    "src.main.get_company_news",
    return_value=[{
        "date": "2026-09-07T16:02:29+00:00",
        "title": "Apple launches new iPhone",
        "text": "Apple unveiled its latest iPhone today.",
        "url": "https://example.com/iphone",
        "symbols": ["AAPL"],
        "source": "The Motley Fool",
    }],
)
def test_news_company_miss_fetches_and_returns(mock_fn, client):
    r = client.get("/news/company/AAPL?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body[0]["title"] == "Apple launches new iPhone"
    assert body[0]["symbols"] == ["AAPL"]
    mock_fn.assert_called_once_with(
        "AAPL", limit=5, start_date=None, end_date=None, provider=None
    )


@patch("src.main.get_company_news", return_value=[])
def test_news_company_no_data_returns_404(mock_fn, client):
    assert client.get("/news/company/UNKNOWN").status_code == 404


@patch("src.main.get_company_news", return_value=[{"title": "x"}])
def test_news_company_hit_returns_cached(mock_fn, client):
    client.get("/news/company/AAPL")
    client.get("/news/company/AAPL")
    assert mock_fn.call_count == 1


def test_news_company_rejects_bad_date_format(client):
    assert client.get("/news/company/AAPL?start_date=nope").status_code == 422


def test_news_company_validates_limit(client):
    assert client.get("/news/company/AAPL?limit=0").status_code == 422


# ---------------------------------------------------------------------------
# Fixed-income routes — D79 19.7
# ---------------------------------------------------------------------------


@patch(
    "src.main.get_bond_ohlcv",
    return_value=[{"date": "2026-01-15", "open": 100.0, "high": 100.5, "low": 99.8, "close": 100.2, "volume": 0}],
)
def test_fixedincome_ohlcv_returns_rows(mock_fn, client):
    r = client.get("/fixedincome/ohlcv/EDO0936?start=2026-01-01&end=2026-06-30")
    assert r.status_code == 200
    assert len(r.json()) == 1
    mock_fn.assert_called_once_with("EDO0936", "2026-01-01", "2026-06-30")


@patch("src.main.get_bond_ohlcv", return_value=None)
def test_fixedincome_ohlcv_not_found_returns_404(mock_fn, client):
    r = client.get("/fixedincome/ohlcv/UNKNOWN?start=2026-01-01&end=2026-06-30")
    assert r.status_code == 404


def test_fixedincome_ohlcv_rejects_bad_date_format(client):
    assert client.get("/fixedincome/ohlcv/EDO0936?start=nope").status_code == 422


@patch(
    "src.main.get_bond_profile",
    return_value={"symbol": "EDO0936", "name": "10-letnie EDO", "maturity_date": "2036-09-15"},
)
def test_fixedincome_profile_returns_record(mock_fn, client):
    r = client.get("/fixedincome/profile/EDO0936")
    assert r.status_code == 200
    assert r.json()["symbol"] == "EDO0936"
    mock_fn.assert_called_once_with("EDO0936")


@patch("src.main.get_bond_profile", return_value=None)
def test_fixedincome_profile_not_found_returns_404(mock_fn, client):
    assert client.get("/fixedincome/profile/UNKNOWN").status_code == 404


@patch("src.main.get_corp_bond_profile", return_value={"symbol": "BST0327", "name": "Best S.A.", "asset_type": "corp_bond"})
def test_corp_bond_profile_returns_record(mock_fn, client):
    r = client.get("/corp-bond/profile/BST0327")
    assert r.status_code == 200
    assert r.json()["symbol"] == "BST0327"
    assert r.json()["asset_type"] == "corp_bond"
    mock_fn.assert_called_once_with("BST0327")


@patch("src.main.get_corp_bond_profile", return_value=None)
def test_corp_bond_profile_not_found_returns_404(mock_fn, client):
    assert client.get("/corp-bond/profile/UNKNOWN").status_code == 404


@patch("src.main.RedisCache.get", return_value=None)
@patch("src.main.RedisCache.set")
@patch(
    "src.importers.corp_bond_catalogue.fetch_catalogue",
    return_value=[{"symbol": "BST0327", "issuer": "Best S.A."}],
)
@patch(
    "src.importers.corp_bond_catalogue.to_tickerref_csv",
    return_value="listing_key,ticker,exchange,name,asset_type,stock_sector,etf_category,country,country_code,isin,aliases\nWSE::BST0327,BST0327,WSE,Best S.A.,corp_bond,,,Poland,PL,,\n",
)
def test_corp_bond_catalogue_returns_csv(mock_csv, mock_rows, mock_set, mock_get, client):
    r = client.get("/corp-bond/catalogue")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "WSE::BST0327" in r.text
    mock_rows.assert_called_once()
    mock_set.assert_called_once()


@patch("src.main.RedisCache.get", return_value=None)
@patch("src.main.RedisCache.set")
@patch("src.importers.corp_bond_catalogue.fetch_catalogue", return_value=[])
def test_corp_bond_catalogue_empty_returns_404(mock_rows, mock_set, mock_get, client):
    assert client.get("/corp-bond/catalogue").status_code == 404


@patch("src.main.RedisCache.get", return_value="cached-csv")
@patch("src.main.RedisCache.set")
def test_corp_bond_catalogue_serves_cache(mock_set, mock_get, client):
    r = client.get("/corp-bond/catalogue")
    assert r.status_code == 200
    assert r.text == "cached-csv"
    mock_set.assert_not_called()


@patch("src.main.search_bonds", return_value=[{"symbol": "EDO0936", "name": "10-letnie EDO"}])
def test_fixedincome_search_returns_results(mock_fn, client):
    r = client.get("/fixedincome/search/EDO")
    assert r.status_code == 200
    assert r.json()[0]["symbol"] == "EDO0936"
    mock_fn.assert_called_once_with("edo")


@patch("src.main.search_bonds", return_value=[])
def test_fixedincome_search_no_results_returns_404(mock_fn, client):
    assert client.get("/fixedincome/search/zzzznope").status_code == 404
