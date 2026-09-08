import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlparse

import httpx
import pandas as pd
from openbb import obb

DIVIDEND_PROVIDERS = ["yfinance", "fmp", "intrinio", "nasdaq"]
METRICS_PROVIDERS  = ["yfinance", "fmp", "intrinio"]
PROFILE_PROVIDERS = ["fmp", "yfinance"]
QUOTE_PROVIDERS = ["fmp", "yfinance", "cboe"]
STATEMENT_PROVIDERS = ["fmp", "yfinance", "polygon", "sec"]
PROJECTION_PROVIDERS = ["fmp", "yfinance", "tmx"]
CALENDAR_PROVIDERS = ["fmp"]
SEARCH_PROVIDERS = ["sec", "nasdaq", "cboe"]
COMPANY_NEWS_PROVIDERS = ["polygon", "fmp", "yfinance"]

STATEMENTS = ("income", "balance", "cash")
PERIODS = ("annual", "quarter")
CALENDAR_KINDS = ("earnings", "dividend")

SEC_PROVIDERS = ["sec"]

logger = logging.getLogger(__name__)

# In-process cache: None = unknown, True/False = confirmed
_pays_dividend: dict[str, bool] = {}

PROVIDER_BLOCK_HOURS = 24.0
_provider_blocked_until: dict[str, datetime] = {}

_RATE_LIMIT_PATTERNS = ("402", "rate limit", "too many requests", "premium", "quota")
_INVALID_TICKER_PATTERNS = (
    "not found for symbol",
    "results not found",
    "no timezone found",
    "possibly delisted",
    "no data found",
)


def _is_rate_limited(err: str) -> bool:
    return any(p in err.lower() for p in _RATE_LIMIT_PATTERNS)


def _is_invalid_ticker(err: str) -> bool:
    return any(p in err.lower() for p in _INVALID_TICKER_PATTERNS)


def _block_provider(provider: str) -> None:
    until = datetime.now(timezone.utc) + timedelta(hours=PROVIDER_BLOCK_HOURS)
    logger.warning("Provider %s rate-limited — blocking until %s", provider, until.isoformat())
    _provider_blocked_until[provider] = until


def _provider_is_blocked(provider: str) -> bool:
    until = _provider_blocked_until.get(provider)
    return until is not None and datetime.now(timezone.utc) < until


def _check_pays_dividend(ticker: str) -> bool:
    """Return True if ticker has any dividend history across all providers."""
    if ticker in _pays_dividend:
        return _pays_dividend[ticker]
    any_success = False
    for provider in DIVIDEND_PROVIDERS:
        if _provider_is_blocked(provider):
            continue
        try:
            df = obb.equity.fundamental.dividends(ticker, provider=provider).to_df()
            any_success = True
            if not df.empty:
                _pays_dividend[ticker] = True
                return True
        except Exception as e:
            err = str(e)
            if _is_rate_limited(err):
                _block_provider(provider)
                continue
            if _is_invalid_ticker(err):
                logger.warning(
                    "Invalid/delisted ticker %s (provider %s) — skipping all providers",
                    ticker,
                    provider,
                )
                _pays_dividend[ticker] = False
                return False
            continue
    if any_success:
        _pays_dividend[ticker] = False
        return False
    return True  # all providers failed — can't confirm non-payer


def get_dividend_yield(ticker: str) -> float | None:
    if _pays_dividend.get(ticker) is False:
        return 0.0
    got_data = False
    for provider in METRICS_PROVIDERS:
        if _provider_is_blocked(provider):
            continue
        try:
            df = obb.equity.fundamental.metrics(ticker, provider=provider).to_df()
            got_data = True
            if df.empty:
                continue
            if "dividend_yield" not in df.columns:
                _pays_dividend[ticker] = False
                return 0.0
            raw = df.iloc[0]["dividend_yield"]
            v = _safe_float(raw, ndigits=4)
            return v if v is not None else 0.0
        except Exception as e:
            err = str(e)
            if _is_rate_limited(err):
                _block_provider(provider)
                continue
            if _is_invalid_ticker(err):
                logger.warning(
                    "Invalid/delisted ticker %s (provider %s) — skipping all providers",
                    ticker,
                    provider,
                )
                _pays_dividend[ticker] = False
                return 0.0
            logger.warning("Provider %s failed for %s: %s", provider, ticker, e)
            continue
    if not got_data and not _check_pays_dividend(ticker):
        return 0.0
    return None


PRICE_PROVIDERS = ["yfinance", "fmp", "intrinio", "polygon", "cboe", "tiingo"]


def get_price_history(ticker: str, start_date: str, end_date: str) -> list[dict] | None:
    for provider in PRICE_PROVIDERS:
        if _provider_is_blocked(provider):
            continue
        try:
            df = obb.equity.price.historical(
                ticker, start_date=start_date, end_date=end_date, provider=provider
            ).to_df()
            if df.empty:
                continue
            rows = []
            for idx, row in df.iterrows():
                date = idx.date() if hasattr(idx, "date") else idx
                close = _safe_float(row.get("close"))
                if close is None:
                    continue
                rows.append({"date": str(date), "close": close})
            return rows
        except Exception as e:
            err = str(e)
            if _is_rate_limited(err):
                _block_provider(provider)
                continue
            if _is_invalid_ticker(err):
                logger.warning("Invalid/delisted ticker %s (provider %s)", ticker, provider)
                return []
            logger.warning("Provider %s failed for %s: %s", provider, ticker, e)
            continue
    return None


def get_dividend_history(ticker: str) -> list[dict] | None:
    if _pays_dividend.get(ticker) is False:
        return []
    any_success = False
    for provider in DIVIDEND_PROVIDERS:
        if _provider_is_blocked(provider):
            continue
        try:
            df = obb.equity.fundamental.dividends(ticker, provider=provider).to_df()
            any_success = True
            if df.empty:
                continue
            # Some providers return the ex-dividend date as a column instead
            # of the index; normalize so we always have a DatetimeIndex.
            if not isinstance(df.index, pd.DatetimeIndex):
                for col in ("date", "ex_dividend_date", "record_date"):
                    if col in df.columns:
                        df = df.set_index(pd.to_datetime(df[col]))
                        break
                else:
                    df.index = pd.to_datetime(df.index, errors="coerce")
            rows = []
            for idx, row in df.iterrows():
                date = idx.date() if hasattr(idx, "date") else idx
                amount = _safe_float(row.get("amount"), ndigits=4)
                if amount is None:
                    continue
                rows.append({"date": str(date), "amount": str(amount)})
            _pays_dividend[ticker] = True
            return rows
        except Exception as e:
            err = str(e)
            if _is_rate_limited(err):
                _block_provider(provider)
                continue
            if _is_invalid_ticker(err):
                logger.warning(
                    "Invalid/delisted ticker %s (provider %s) — skipping all providers",
                    ticker,
                    provider,
                )
                _pays_dividend[ticker] = False
                return []
            logger.warning("Provider %s failed for %s: %s", provider, ticker, e)
            continue
    if any_success:
        _pays_dividend[ticker] = False
    return []


def _plain(value):
    """Convert a pandas/numpy cell into a JSON-safe primitive."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, (int, float, str, bool)):
        return value
    return str(value)


def _safe_float(value, ndigits: int = 4) -> float | None:
    """Round and return a float, or None for NaN/None/non-numeric values."""
    v = _plain(value)
    if v is None:
        return None
    try:
        return round(float(v), ndigits)
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> int | None:
    """Return an int, or None for NaN/None/non-numeric values."""
    v = _plain(value)
    if v is None:
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _df_records(df: "pd.DataFrame") -> list[dict]:
    if df.index.name is None:
        df = df.reset_index(drop=True)
    else:
        df = df.reset_index()
    return [{str(k): _plain(v) for k, v in row.items()} for _, row in df.iterrows()]


def _df_single_long_records(df: "pd.DataFrame") -> dict | None:
    """Return the single record from an OpenBB to_df() result.

    Most OpenBB endpoints return a wide frame where every row is one record;
    management_discussion_analysis returns a *long* two-column frame
    (``index`` field labels mapped to a single value column), i.e. one row per
    field. Pivot the long shape back into {field: value} and fall back to the
    wide frame otherwise.
    """
    cols = list(df.columns)
    if len(cols) == 2 and str(cols[0]).lower() == "index":
        value_col = cols[1]
        return {str(k): _plain(v) for k, v in zip(df[cols[0]], df[value_col])}
    records = _df_records(df)
    return records[0] if records else None


def _single_record(providers, call, ticker: str) -> dict | None:
    got_data = False
    for provider in providers:
        if _provider_is_blocked(provider):
            continue
        try:
            df = call(provider).to_df()
            got_data = True
            if df.empty:
                continue
            records = _df_records(df)
            if records:
                return records[0]
            continue
        except Exception as e:
            err = str(e)
            if _is_rate_limited(err):
                _block_provider(provider)
                continue
            if _is_invalid_ticker(err):
                logger.warning("Invalid/delisted ticker %s (provider %s)", ticker, provider)
                return None
            logger.warning("Provider %s failed for %s: %s", provider, ticker, e)
            continue
    return None


def get_profile(ticker: str) -> dict | None:
    return _single_record(
        PROFILE_PROVIDERS,
        lambda provider: obb.equity.profile(ticker, provider=provider),
        ticker,
    )


def get_quote(ticker: str) -> dict | None:
    return _single_record(
        QUOTE_PROVIDERS,
        lambda provider: obb.equity.price.quote(ticker, provider=provider),
        ticker,
    )


def get_metrics(ticker: str) -> dict | None:
    return _single_record(
        METRICS_PROVIDERS,
        lambda provider: obb.equity.fundamental.metrics(ticker, provider=provider),
        ticker,
    )


def get_projections(ticker: str) -> dict | None:
    base = _single_record(
        PROJECTION_PROVIDERS,
        lambda provider: obb.equity.estimates.consensus(ticker, provider=provider),
        ticker,
    )
    if base is None:
        return None
    # Best-effort analyst recommendation from yfinance (mean on the 1..5
    # sell->strong-buy scale plus analyst count). Free tier has no bucket
    # breakdown, so only mean/count are exposed.
    try:
        df = obb.equity.estimates.consensus(ticker, provider="yfinance").to_df()
        row = df.iloc[0]
        rec_mean = _plain(row.get("recommendation_mean"))
        analysts = _plain(row.get("number_of_analysts"))
        rating = _plain(row.get("recommendation"))
        base["recommendation"] = {
            "mean": round(float(rec_mean), 2) if isinstance(rec_mean, (int, float)) else None,
            "rating": str(rating) if rating else None,
            "analysts": int(analysts) if isinstance(analysts, (int, float)) else None,
        }
    except Exception as e:
        logger.warning("yfinance recommendation unavailable for %s: %s", ticker, e)
        base["recommendation"] = None
    return base


def get_ohlcv_history(ticker: str, start_date: str, end_date: str) -> list[dict] | None:
    for provider in PRICE_PROVIDERS:
        if _provider_is_blocked(provider):
            continue
        try:
            df = obb.equity.price.historical(
                ticker, start_date=start_date, end_date=end_date, provider=provider
            ).to_df()
            if df.empty:
                continue
            rows = []
            for idx, row in df.iterrows():
                date = idx.date() if hasattr(idx, "date") else idx
                close = _safe_float(row.get("close"))
                if close is None:
                    continue  # skip rows with NaN close — unusable
                rows.append({
                    "date": str(date),
                    "open": _safe_float(row.get("open")) or close,
                    "high": _safe_float(row.get("high")) or close,
                    "low": _safe_float(row.get("low")) or close,
                    "close": close,
                    "volume": _safe_int(row.get("volume")) or 0,
                })
            return rows
        except Exception as e:
            err = str(e)
            if _is_rate_limited(err):
                _block_provider(provider)
                continue
            if _is_invalid_ticker(err):
                logger.warning("Invalid/delisted ticker %s (provider %s)", ticker, provider)
                return []
            logger.warning("Provider %s failed for %s: %s", provider, ticker, e)
            continue
    return None


def get_fundamentals(ticker: str, statement: str, period: str) -> list[dict]:
    fn = getattr(obb.equity.fundamental, statement)
    for provider in STATEMENT_PROVIDERS:
        if _provider_is_blocked(provider):
            continue
        try:
            df = fn(ticker, period=period, provider=provider).to_df()
            if df.empty:
                continue
            records = _df_records(df)
            if records:
                return records
            continue
        except Exception as e:
            err = str(e)
            if _is_rate_limited(err):
                _block_provider(provider)
                continue
            if _is_invalid_ticker(err):
                logger.warning("Invalid/delisted ticker %s (provider %s)", ticker, provider)
                return []
            logger.warning("Provider %s failed for %s: %s", provider, ticker, e)
            continue
    return []


def get_calendar(kind: str, start_date: str, end_date: str) -> list[dict]:
    fn = getattr(obb.equity.calendar, kind)
    for provider in CALENDAR_PROVIDERS:
        if _provider_is_blocked(provider):
            continue
        try:
            df = fn(start_date=start_date, end_date=end_date, provider=provider).to_df()
            if df.empty:
                continue
            records = _df_records(df)
            if records:
                return records
            continue
        except Exception as e:
            err = str(e)
            if _is_rate_limited(err):
                _block_provider(provider)
                continue
            if _is_invalid_ticker(err):
                return []
            logger.warning("Provider %s failed for calendar/%s: %s", provider, kind, e)
            continue
    return []


def search_equities(query: str) -> list[dict]:
    for provider in SEARCH_PROVIDERS:
        if _provider_is_blocked(provider):
            continue
        try:
            df = obb.equity.search(query, provider=provider).to_df()
            if df.empty:
                continue
            records = _df_records(df)
            if records:
                return records
            continue
        except Exception as e:
            err = str(e)
            if _is_rate_limited(err):
                _block_provider(provider)
                continue
            logger.warning("Provider %s failed for search '%s': %s", provider, query, e)
            continue
    return []


def _split_symbols(value) -> list[str]:
    """Normalize an OpenBB `symbols` cell (comma string or list) to a symbol list."""
    if isinstance(value, (list, tuple)):
        out = []
        for s in value:
            s = _plain(s)
            if s:
                out.append(str(s).strip().upper())
        return out
    value = _plain(value)  # NaN -> None
    if value is None:
        return []
    return [s.strip().upper() for s in str(value).split(",") if s.strip()]


def _news_source(row) -> str | None:
    """Resolve the news outlet name: prefer `publisher.name`, else the author string."""
    pub = row.get("publisher")
    if isinstance(pub, dict):
        name = pub.get("name")
        if name:
            return str(name)
    src = _plain(row.get("source"))
    return str(src) if src else None


def get_company_news(
    ticker: str,
    limit: int = 50,
    start_date: str | None = None,
    end_date: str | None = None,
    provider: str | None = None,
) -> list[dict]:
    """Company news articles, provider-fallback across COMPANY_NEWS_PROVIDERS.

    Records map to ``{date, title, text, url, symbols, source}``. ``symbols`` is
    normalized to a list (empty when the provider omits it); ``source`` is the
    outlet (publisher name, else author). OpenBB's day-granularity
    start/end dates mean the URL-primary-key dedup in the instruments layer
    absorbs overlapping windows.
    """
    providers = [provider] if provider else COMPANY_NEWS_PROVIDERS
    for p in providers:
        if _provider_is_blocked(p):
            continue
        try:
            kwargs = {}
            if start_date:
                kwargs["start_date"] = start_date
            if end_date:
                kwargs["end_date"] = end_date
            df = obb.news.company(symbol=ticker, limit=limit, provider=p, **kwargs).to_df()
            if df.empty:
                continue
            rows = []
            for idx, row in df.iterrows():
                date = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
                rows.append({
                    "date": date,
                    "title": _plain(row.get("title")),
                    "text": _plain(row.get("text")),
                    "url": _plain(row.get("url")),
                    "symbols": _split_symbols(row.get("symbols")),
                    "source": _news_source(row),
                })
            if rows:
                return rows
            continue
        except Exception as e:
            err = str(e)
            if _is_rate_limited(err):
                _block_provider(p)
                continue
            if _is_invalid_ticker(err):
                logger.warning("Invalid/delisted ticker %s (provider %s)", ticker, p)
                return []
            logger.warning("Provider %s failed company news for %s: %s", p, ticker, e)
            continue
    return []


def get_insider_trading(ticker: str) -> list[dict]:
    """SEC Form 4 insider transactions (director/officer purchases & sales)."""
    for provider in SEC_PROVIDERS:
        if _provider_is_blocked(provider):
            continue
        try:
            df = obb.equity.ownership.insider_trading(ticker, provider=provider).to_df()
            if df.empty:
                continue
            records = _df_records(df)
            if records:
                return records
            continue
        except Exception as e:
            err = str(e)
            if _is_rate_limited(err):
                _block_provider(provider)
                continue
            if _is_invalid_ticker(err):
                logger.warning("Invalid/delisted ticker %s (provider %s)", ticker, provider)
                return []
            logger.warning("Provider %s failed insider_trading for %s: %s", provider, ticker, e)
            continue
    return []


def get_institutional_ownership(ticker: str) -> list[dict]:
    """SEC Form 13F institutional holdings (filed quarterly by $100M+ AUM managers)."""
    for provider in SEC_PROVIDERS:
        if _provider_is_blocked(provider):
            continue
        try:
            df = obb.equity.ownership.form_13f(ticker, provider=provider).to_df()
            if df.empty:
                continue
            records = _df_records(df)
            if records:
                return records
            continue
        except Exception as e:
            err = str(e)
            if _is_rate_limited(err):
                _block_provider(provider)
                continue
            if _is_invalid_ticker(err):
                logger.warning("Invalid/delisted ticker %s (provider %s)", ticker, provider)
                return []
            logger.warning("Provider %s failed form_13f for %s: %s", provider, ticker, e)
            continue
    return []


def get_filings(ticker: str) -> list[dict]:
    """SEC EDGAR filing index (10-K, 10-Q, 8-K, etc.) with access URLs."""
    for provider in SEC_PROVIDERS:
        if _provider_is_blocked(provider):
            continue
        try:
            df = obb.equity.fundamental.filings(ticker, provider=provider).to_df()
            if df.empty:
                continue
            records = _df_records(df)
            if records:
                return records
            continue
        except Exception as e:
            err = str(e)
            if _is_rate_limited(err):
                _block_provider(provider)
                continue
            if _is_invalid_ticker(err):
                logger.warning("Invalid/delisted ticker %s (provider %s)", ticker, provider)
                return []
            logger.warning("Provider %s failed filings for %s: %s", provider, ticker, e)
            continue
    return []


def get_mda(ticker: str) -> dict | None:
    """Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only)."""
    for provider in SEC_PROVIDERS:
        if _provider_is_blocked(provider):
            continue
        try:
            df = obb.equity.fundamental.management_discussion_analysis(ticker, provider=provider).to_df()
            if df.empty:
                continue
            record = _df_single_long_records(df)
            if record:
                return record
            continue
        except Exception as e:
            err = str(e)
            if _is_rate_limited(err):
                _block_provider(provider)
                continue
            if _is_invalid_ticker(err):
                logger.warning("Invalid/delisted ticker %s (provider %s)", ticker, provider)
                return None
            logger.warning("Provider %s failed management_discussion_analysis for %s: %s", provider, ticker, e)
            continue
    return None


_FAVICON_URL = "https://www.google.com/s2/favicons?domain={domain}&sz=128"


def get_logo(ticker: str) -> dict | None:
    """Resolve a logo URL for the ticker via the D34 chain.

    1. FMP keyless CDN (images.financialmodelingprep.com) — strong coverage.
    2. Profile website (yfinance `company_url`, then fmp) → Google favicon.

    Returns {"source", "remote_url"} or None when the chain is exhausted. The
    caller owns downloading and persisting bytes; openst stays a thin wrapper.
    """
    t = ticker.strip().upper()
    fmp_url = f"https://images.financialmodelingprep.com/symbol/{t}.png"
    try:
        resp = httpx.head(fmp_url, timeout=10)
        if resp.status_code == 200:
            return {"source": "fmp", "remote_url": fmp_url}
    except Exception as e:
        logger.warning("FMP logo probe failed for %s: %s", ticker, e)

    website = None
    for provider in ("yfinance", "fmp"):
        if _provider_is_blocked(provider):
            continue
        try:
            df = obb.equity.profile(ticker, provider=provider).to_df()
            if df.empty:
                continue
            for col in ("company_url", "website"):
                value = _plain(df.iloc[0].get(col))
                if value:
                    website = str(value)
                    break
            if website:
                break
        except Exception as e:
            err = str(e)
            if _is_rate_limited(err):
                _block_provider(provider)
                continue
            logger.warning("Provider %s failed logo profile for %s: %s", provider, ticker, e)
            continue

    domain = urlparse(website or "").hostname
    if not domain:
        return None
    return {"source": "favicon", "remote_url": _FAVICON_URL.format(domain=domain)}
