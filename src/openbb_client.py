import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from openbb import obb

DIVIDEND_PROVIDERS = ["yfinance", "fmp", "intrinio", "nasdaq"]
METRICS_PROVIDERS  = ["yfinance", "fmp", "intrinio"]

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
