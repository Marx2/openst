import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd
from openbb import obb

DIVIDEND_PROVIDERS = ["yfinance", "fmp", "intrinio", "nasdaq"]
METRICS_PROVIDERS  = ["yfinance", "fmp", "intrinio"]
PROFILE_PROVIDERS = ["fmp", "yfinance"]
QUOTE_PROVIDERS = ["fmp", "yfinance"]
STATEMENT_PROVIDERS = ["fmp", "yfinance"]
PROJECTION_PROVIDERS = ["fmp", "yfinance"]
CALENDAR_PROVIDERS = ["fmp"]
SEARCH_PROVIDERS = ["sec"]

STATEMENTS = ("income", "balance", "cash")
PERIODS = ("annual", "quarter")
CALENDAR_KINDS = ("earnings", "dividend")

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
            return float(Decimal(str(raw)).quantize(Decimal("0.01")))
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


PRICE_PROVIDERS = ["yfinance", "fmp", "intrinio"]


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
                rows.append({"date": str(date), "close": float(round(row["close"], 4))})
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
                amount = str(Decimal(str(row["amount"])).quantize(Decimal("0.0001")))
                rows.append({"date": str(date), "amount": amount})
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


def _df_records(df: "pd.DataFrame") -> list[dict]:
    if df.index.name is None:
        df = df.reset_index(drop=True)
    else:
        df = df.reset_index()
    return [{str(k): _plain(v) for k, v in row.items()} for _, row in df.iterrows()]


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
                rows.append({
                    "date": str(date),
                    "open": float(round(row["open"], 4)),
                    "high": float(round(row["high"], 4)),
                    "low": float(round(row["low"], 4)),
                    "close": float(round(row["close"], 4)),
                    "volume": int(row["volume"]),
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
