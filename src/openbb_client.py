import logging
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from urllib.parse import urlparse

import httpx
import pandas as pd
from openbb import obb

from src import db

DIVIDEND_PROVIDERS = ["nasdaq", "yfinance", "fmp", "intrinio", "dividendmax"]
METRICS_PROVIDERS  = ["yfinance", "fmp", "intrinio"]
PROFILE_PROVIDERS = ["fmp", "yfinance", "biznesradar"]
QUOTE_PROVIDERS = ["fmp", "yfinance", "cboe", "biznesradar"]
STATEMENT_PROVIDERS = ["fmp", "yfinance", "polygon", "sec"]
SPLIT_PROVIDERS = ["fmp"]
PROJECTION_PROVIDERS = ["fmp", "yfinance", "tmx"]
# biznesradar only implements CalendarDividend (GPW coupon/payment calendar,
# §52) — it is NOT a valid provider for the Earnings model, so earnings uses
# its own list (OpenBB Earnings accepts fmp/nasdaq/tmx).
CALENDAR_PROVIDERS = {"dividend": ["fmp", "nasdaq", "biznesradar"], "earnings": ["fmp", "nasdaq", "tmx"]}
SEARCH_PROVIDERS = ["sec", "nasdaq", "cboe", "biznesradar"]
COMPANY_NEWS_PROVIDERS = ["polygon", "fmp", "yfinance"]

STATEMENTS = ("income", "balance", "cash")
PERIODS = ("annual", "quarter")
CALENDAR_KINDS = ("earnings", "dividend")

SEC_PROVIDERS = ["sec"]

logger = logging.getLogger(__name__)

# In-process cache: ticker -> whether it has any dividend history.
# Bounded because the ticker is attacker-controlled (the routes are unauthenticated),
# so the key space is unbounded; a plain dict would grow for the life of the process.
_pays_dividend: dict[str, bool] = {}

# Above this many tracked tickers the least-recently-added entries are dropped. Real
# usage is a few thousand instruments, so this only trips under scanning/fuzzing, and
# dropping an entry costs one extra provider walk rather than any correctness.
PAYS_DIVIDEND_MAX = 20_000


def _remember_pays_dividend(ticker: str, pays: bool) -> None:
    """Record a ticker in the bounded dividend cache."""
    if len(_pays_dividend) >= PAYS_DIVIDEND_MAX and ticker not in _pays_dividend:
        # dict preserves insertion order, so the head is the oldest entry.
        for stale in list(_pays_dividend)[: len(_pays_dividend) - PAYS_DIVIDEND_MAX + 1]:
            _pays_dividend.pop(stale, None)
    _pays_dividend[ticker] = pays

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


# What a provider-walk loop should do after a provider raised.
class _Action(Enum):
    NEXT = "next"    # try the following provider
    STOP = "stop"    # stop walking; the caller returns its own "invalid symbol" value


def _classify(provider_error: Exception, provider: str, subject: str) -> _Action:
    """Decide what a provider-walk loop does about an exception, and log it once.

    The policy — throttle means block-and-move-on, an unknown symbol means stop
    walking, anything else means warn and try the next provider — was duplicated
    across ~15 loops, so it could drift between routes. What a route returns for an
    unknown symbol is deliberately *not* decided here: an empty list is a 200 while
    None is a 404, and that difference is per-route and load-bearing.
    """
    err = str(provider_error)
    if _is_rate_limited(err):
        _block_provider(provider)
        return _Action.NEXT
    if _is_invalid_ticker(err):
        logger.warning("Invalid/delisted %s (provider %s)", subject, provider)
        return _Action.STOP
    logger.warning("Provider %s failed for %s: %s", provider, subject, provider_error)
    return _Action.NEXT


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
                _remember_pays_dividend(ticker, True)
                return True
        except Exception as e:
            if _classify(e, provider, ticker) is _Action.STOP:
                _remember_pays_dividend(ticker, False)
                return False
            continue
    if any_success:
        _remember_pays_dividend(ticker, False)
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
                _remember_pays_dividend(ticker, False)
                return 0.0
            raw = df.iloc[0]["dividend_yield"]
            v = _safe_float(raw, ndigits=2)
            return v if v is not None else 0.0
        except Exception as e:
            if _classify(e, provider, ticker) is _Action.STOP:
                _remember_pays_dividend(ticker, False)
                return 0.0
            continue
    if not got_data and not _check_pays_dividend(ticker):
        return 0.0
    return None


# Last-resort fallback for PL-venue symbols (funds/bonds) that free US venues
# don't cover. biznesradar reads BIZNESRADAR_FETCH_DELAY_S straight from env in
# its fetcher — no extra plumbing needed here.
PRICE_PROVIDERS = ["yfinance", "fmp", "intrinio", "polygon", "cboe", "tiingo", "biznesradar"]

# Memoised provider-declared currency per ticker, so the pence check below costs
# at most one quote fetch per symbol per process. Only successful lookups are
# cached: a None is a transient failure and must be retried, not remembered.
#
# §73.4 — BOUNDED, for the same reason `_pays_dividend` twenty lines above is
# bounded: these routes are unauthenticated, so the ticker is caller-controlled
# and the key space is unbounded. A plain dict here grows for the life of the
# process, and the sweep paths in particular walk the alphabet.
#
# This is NOT the §73 memory leak and is not offered as its cause. 400 real
# tickers of a short string is tens of kilobytes, and the measured curve is
# hundreds of megabytes — four orders of magnitude away. It is fixed because an
# unbounded caller-keyed dict on an unauthenticated route is a defect on its own
# (spray N random tickers, grow the heap by N), not because it explains anything
# about the OOMKills. §73.4's cause is still to be found by measurement.
_symbol_currency_cache: dict[str, str | None] = {}

# Real usage is a few thousand instruments, so this only trips under scanning or
# fuzzing, and dropping an entry costs one extra quote fetch rather than any
# correctness — the same trade `_remember_pays_dividend` makes.
SYMBOL_CURRENCY_MAX = 20_000


def _remember_symbol_currency(ticker: str, currency: str) -> None:
    """Record a resolved currency in the bounded currency cache."""
    if len(_symbol_currency_cache) >= SYMBOL_CURRENCY_MAX and ticker not in _symbol_currency_cache:
        # dict preserves insertion order, so the head is the oldest entry.
        for stale in list(_symbol_currency_cache)[: len(_symbol_currency_cache) - SYMBOL_CURRENCY_MAX + 1]:
            _symbol_currency_cache.pop(stale, None)
    _symbol_currency_cache[ticker] = currency


def _is_pence_currency(currency: str | None) -> bool:
    """True for pence-denominated currency labels.

    OpenBB/yfinance labels LSE pence quotes "GBp"; the ISO code "GBP" collides
    once lowercased, so the comparison is case-sensitive and excludes "GBP"
    exactly (same rule as portfoliost-instruments' `isPence`).
    """
    if not currency:
        return False
    if currency == "GBP":
        return False
    return currency[:2].upper() == "GB"


def _symbol_currency(ticker: str) -> str | None:
    """Provider-declared currency for `ticker`, or None if it can't be determined."""
    key = (ticker or "").upper()
    if key in _symbol_currency_cache:
        return _symbol_currency_cache[key]
    try:
        quote = get_quote(ticker) or {}
        currency = quote.get("currency") or None
    except Exception as e:  # a failed lookup must not be cached
        logger.warning("currency lookup unavailable for %s: %s", ticker, e)
        return None
    if currency:
        _remember_symbol_currency(key, currency)
    return currency


def _needs_gbx_normalization(provider: str, ticker: str) -> bool:
    """yfinance quotes *pence* LSE (London, `.L`) lines in GBX (pence/100).

    BYG.L 820 = £8.20 (2026-09-25 PROD incident — 100× chart inflation,
    plan §63.5). Every other source in the system (the quote path, stooq UK)
    uses major units, so yfinance LSE history must be normalized to the major
    unit before it reaches price_bars.

    The `.L` suffix alone is NOT sufficient. Plenty of LSE lines are quoted in
    USD (CNYA.L, DEAM.L, EMQQ.L, IUFS.L, SMH.L, …) and yfinance returns those
    in major units already — dividing them produced 100× too small bars
    (CNYA.L 0.0447 for a fund that trades ~4.46; DEAM.L 0.583 for ~58.3;
    IWDA.L 1.4691 for ~146.9). So the currency the provider reports decides,
    not the ticker suffix.

    When the currency cannot be determined we deliberately do NOT scale: a
    missed scale on a genuine pence line is a bounded 100× on a symbol that
    instruments also flags, whereas scaling a USD line is an unbounded error
    on a whole class of ETFs.
    """
    if provider != "yfinance":
        return False
    if not (ticker or "").upper().endswith(".L"):
        return False
    return _is_pence_currency(_symbol_currency(ticker))


def _gbx_to_gbp(rows: list[dict]) -> list[dict]:
    """Divide every price field of a pence-denominated row set by 100."""
    for r in rows:
        for k in ("open", "high", "low", "close"):
            v = r.get(k)
            if v is not None:
                r[k] = v / 100.0
    return rows


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
            if _needs_gbx_normalization(provider, ticker):
                rows = _gbx_to_gbp(rows)
            return rows
        except Exception as e:
            if _classify(e, provider, ticker) is _Action.STOP:
                return []
            continue
    return None


def _forecast_status(raw: str | None) -> bool:
    if raw is None:
        return False
    s = raw.strip().lower()
    return any(k in s for k in ("forecast", "predicted", "rekomendowana"))


def _normalise_dividend_df(df, today: str) -> list[dict]:
    """Flatten an equity.fundamental.dividends dataframe into pay/forecast rows.

    Paid/declared rows keep the historical shape ``{date, amount, payment_date?}``
    (see #52); rows the provider marks as forecast/predicted are kept with
    ``status`` set and no ``amount`` — dividendmax's amount cell is gated behind
    sign-up, so a real number will never be present anyway. The `payload` path in
    the store maps that to status='predicted', amount=NULL.
    """
    if df.empty:
        return []
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
        raw_status = row.get("status")
        if _forecast_status(raw_status if isinstance(raw_status, str) else None):
            item = {"date": str(date), "status": raw_status}
            payment_date = row.get("payment_date")
            if payment_date is not None and not pd.isna(payment_date):
                try:
                    item["payment_date"] = str(pd.Timestamp(payment_date).date())
                except (ValueError, TypeError):
                    pass
            if row.get("declaration_date") is not None and not pd.isna(row.get("declaration_date")):
                try:
                    item["declaration_date"] = str(pd.Timestamp(row["declaration_date"]).date())
                except (ValueError, TypeError):
                    pass
            if row.get("currency") is not None and not pd.isna(row.get("currency")):
                item["currency"] = str(row["currency"])
            rows.append(item)
            continue
        amount = _safe_float(row.get("amount"), ndigits=4)
        if amount is None:
            continue
        item = {"date": str(date), "amount": f"{amount:.4f}"}
        payment_date = row.get("payment_date")
        if payment_date is not None and not pd.isna(payment_date):
            try:
                item["payment_date"] = str(pd.Timestamp(payment_date).date())
            except (ValueError, TypeError):
                pass
        if isinstance(raw_status, str) and raw_status.strip():
            item["status"] = raw_status
        rows.append(item)
    return rows


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
            rows = _normalise_dividend_df(df, "today")
            if provider != "dividendmax":
                # Even when nasdaq keeps the paid history, dividendmax's page
                # carries the declared forecast dates that nasdaq/yfinance never
                # return — union-merge into the same response, deduping by date.
                try:
                    fx = obb.equity.fundamental.dividends(ticker, provider="dividendmax").to_df()
                    if not fx.empty:
                        known = {r.get("date") for r in rows}
                        for fr in _normalise_dividend_df(fx, "today"):
                            st = fr.get("status")
                            if st is None:
                                continue
                            s = st.strip().lower()
                            # Forecast rows (dates only) and declared rows
                            # (public amount) are what dividendmax knows and
                            # nasdaq/yfinance never return. Paid rows are
                            # skipped: the primary provider already has them.
                            if _forecast_status(st) or "declar" in s:
                                if fr["date"] not in known:
                                    rows.append(fr)
                                    known.add(fr["date"])
                except Exception:
                    pass
            _remember_pays_dividend(ticker, True)
            return rows
        except Exception as e:
            if _classify(e, provider, ticker) is _Action.STOP:
                _remember_pays_dividend(ticker, False)
                return []
            continue
    if any_success:
        _remember_pays_dividend(ticker, False)
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


def get_historical_splits(ticker: str) -> dict:
    """Return normalized split events and provider coverage status.

    OpenBB's historical-splits model currently exposes FMP only. A provider
    failure is deliberately returned as ``unsupported``/``unavailable`` rather
    than being mistaken for a confirmed empty history.
    """
    for provider in SPLIT_PROVIDERS:
        if _provider_is_blocked(provider):
            continue
        try:
            df = obb.equity.fundamental.historical_splits(ticker, provider=provider).to_df()
            if df.empty:
                return {"status": "confirmed_empty", "provider": provider, "events": []}

            events: list[dict] = []
            for row in _df_records(df):
                raw_date = row.get("date") or row.get("effective_date")
                numerator = _safe_float(row.get("numerator"), ndigits=8)
                denominator = _safe_float(row.get("denominator"), ndigits=8)
                if raw_date is None or numerator is None or denominator is None:
                    return {
                        "status": "malformed",
                        "provider": provider,
                        "events": [],
                    }
                if numerator <= 0 or denominator <= 0:
                    return {"status": "malformed", "provider": provider, "events": []}
                effective_date = str(raw_date)
                factor = round(numerator / denominator, 8)
                events.append({
                    "symbol": ticker.upper(),
                    "effectiveDate": effective_date,
                    "numerator": numerator,
                    "denominator": denominator,
                    "factor": factor,
                    "splitType": row.get("splitType"),
                    "provider": provider,
                    "evidence": row,
                })
            return {"status": "confirmed", "provider": provider, "events": events}
        except Exception as e:
            action = _classify(e, provider, ticker)
            if _is_rate_limited(str(e)):
                continue
            logger.warning("Split provider unavailable for %s: %s", ticker, e)
            return {
                "status": "unsupported" if _is_invalid_ticker(str(e)) else "unavailable",
                "provider": provider,
                "events": [],
            }
    return {"status": "unavailable", "provider": None, "events": []}


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
            _classify(e, provider, ticker)
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


def _ohlcv_row(idx, row) -> dict | None:
    """Build one OHLCV record, or None when the bar has no usable close.

    open/high/low fall back to close when *absent*, never when zero: `x or close`
    would rewrite a legitimate 0.0 as the close price.
    """
    close = _safe_float(row.get("close"))
    if close is None:
        return None

    def price(field: str) -> float:
        value = _safe_float(row.get(field))
        return close if value is None else value

    return {
        "date": str(idx.date() if hasattr(idx, "date") else idx),
        "open": price("open"),
        "high": price("high"),
        "low": price("low"),
        "close": close,
        "volume": _safe_int(row.get("volume")) or 0,
    }


def _ohlcv_rows(df) -> list[dict]:
    """Build OHLCV records from a frame, dropping bars with no usable close."""
    rows = []
    for idx, row in df.iterrows():
        built = _ohlcv_row(idx, row)
        if built is not None:
            rows.append(built)
    return rows


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
            rows = _ohlcv_rows(df)
            if _needs_gbx_normalization(provider, ticker):
                rows = _gbx_to_gbp(rows)
            return rows
        except Exception as e:
            if _classify(e, provider, ticker) is _Action.STOP:
                return []
            continue
    return None


CRYPTO_PROVIDERS = ["yfinance", "fmp", "tiingo"]
CRYPTO_SEARCH_PROVIDERS = ["fmp"]  # fmp is the only provider exposing crypto.search
_CRYPTO_KEY_ENV = {"fmp": "FMP_API_KEY", "tiingo": "TIINGO_TOKEN"}

# A quote only needs the last two bars, so the history fetch is windowed instead of
# pulling every bar since inception for every quote request.
CRYPTO_QUOTE_WINDOW_DAYS = 30


def _provider_has_key(provider: str) -> bool:
    """Crypto providers requiring a key are only tried when the key is set."""
    env = _CRYPTO_KEY_ENV.get(provider)
    return env is None or bool(os.environ.get(env))


def get_crypto_ohlcv(pair: str, start_date: str, end_date: str) -> list[dict] | None:
    for provider in CRYPTO_PROVIDERS:
        if _provider_is_blocked(provider) or not _provider_has_key(provider):
            continue
        try:
            df = obb.crypto.price.historical(
                pair, start_date=start_date, end_date=end_date, provider=provider
            ).to_df()
            if df.empty:
                continue
            return _ohlcv_rows(df)
        except Exception as e:
            _classify(e, provider, pair)
            continue
    return None


def get_crypto_quote(pair: str) -> dict | None:
    """Latest quote, derived from the last two bars.

    Fetches a short window rather than the full history: only two bars are used, and
    pulling every bar since inception for a quote is slow and grows without bound.
    """
    end = date.today()
    start = end - timedelta(days=CRYPTO_QUOTE_WINDOW_DAYS)
    for provider in CRYPTO_PROVIDERS:
        if _provider_is_blocked(provider) or not _provider_has_key(provider):
            continue
        try:
            df = obb.crypto.price.historical(
                pair, start_date=str(start), end_date=str(end), provider=provider
            ).to_df()
            if df.empty:
                continue
            rows = _ohlcv_rows(df)
            if not rows:
                continue
            latest = rows[-1]
            quote = {
                "symbol": pair,
                "price": latest["close"],
                "open": latest["open"],
                "high": latest["high"],
                "low": latest["low"],
                "volume": latest["volume"],
                "date": latest["date"],
            }
            if len(rows) >= 2:
                prev_close = rows[-2]["close"]
                change = round(latest["close"] - prev_close, 4)
                quote["change"] = change
                quote["change_percent"] = round(change / prev_close, 2) if prev_close else None
            return quote
        except Exception as e:
            _classify(e, provider, pair)
            continue
    return None


CRYPTO_PROFILE_SEARCH_FIELDS = (
    "name",
    "exchange",
    "ico_date",
    "circulating_supply",
    "total_supply",
)


def _crypto_search_row(pair: str) -> dict | None:
    """The one crypto-search row that is exactly ``pair``, or ``None``.

    The search leg filters with ``str.contains``, so it returns every symbol that
    embeds the query: ``BTC`` matches ``TBTCUSD`` (row 1) as well as ``BTCUSD``
    (row 12). Taking the first row would file tBTC USD's supply under Bitcoin's
    name, which is worse than no name at all.

    The dash is stripped on both sides because the provider does not spell the
    pair the way we ask for it — FMP returns ``BTCUSD`` for ``BTC-USD`` — so a
    literal comparison matches nothing for any real pair (§86.1).
    """
    wanted = pair.upper().replace("-", "")
    for provider in CRYPTO_SEARCH_PROVIDERS:
        if _provider_is_blocked(provider) or not _provider_has_key(provider):
            continue
        try:
            df = obb.crypto.search(pair, provider=provider).to_df()
            if df.empty:
                continue
            records = _df_records(df)
        except Exception as e:
            # Free-text search has no invalid-symbol concept, so — exactly as in
            # get_crypto_search — every failure just moves to the next provider.
            # A profile without a name is still a profile.
            _classify(e, provider, pair)
            continue
        for row in records:
            if str(row.get("symbol", "")).upper().replace("-", "") == wanted:
                return row
    return None


def get_crypto_profile(pair: str) -> dict | None:
    """Quote-derived price/currency plus the search leg's name and supply.

    The body is still derived from the quote (there is no dedicated crypto
    profile endpoint), but the fields a price bar cannot carry are merged on from
    the search leg, which already runs against the only provider with crypto
    metadata. Keys the search row does not have are omitted rather than emitted
    as null, so a key is never permanently empty (§86.1).
    """
    quote = get_crypto_quote(pair)
    if quote is None:
        return None
    parts = pair.upper().split("-")
    profile = {
        "symbol": pair,
        "currency": parts[-1] if len(parts) > 1 else None,
        "price": quote.get("price"),
        "date": quote.get("date"),
    }
    row = _crypto_search_row(pair)
    if row is not None:
        for field in CRYPTO_PROFILE_SEARCH_FIELDS:
            if field in row:
                # A missing supply stays None and is never coerced to 0: FMP
                # omits it for six of the seventeen btcusd-matching rows.
                profile[field] = row[field]
    return profile


def get_crypto_search(query: str) -> list[dict]:
    for provider in CRYPTO_SEARCH_PROVIDERS:
        if _provider_is_blocked(provider) or not _provider_has_key(provider):
            continue
        try:
            df = obb.crypto.search(query, provider=provider).to_df()
            if df.empty:
                continue
            records = _df_records(df)
            if records:
                return records
            continue
        except Exception as e:
            # No invalid-symbol concept for a free-text search: always try the next
            # provider, whatever the failure was.
            _classify(e, provider, query)
            continue
    return []


# ---------------------------------------------------------------------------
# Polish retail savings bonds (D79) — obligacje provider
# ---------------------------------------------------------------------------


def get_bond_ohlcv(symbol: str, start_date: str, end_date: str) -> list[dict] | None:
    """Priced redemption OHLCV series for a savings-bond emission (D79 19.7).

    Calls ``obb.equity.price.historical`` with ``provider="obligacje"``.
    Returns ``None`` when the symbol is unknown or the DB is unavailable.
    """
    try:
        df = obb.equity.price.historical(
            symbol, start_date=start_date, end_date=end_date, provider="obligacje"
        ).to_df()
        if df.empty:
            return None
        rows = _ohlcv_rows(df)
        return rows or None
    except Exception as e:
        logger.warning("obligacje OHLCV failed for %s: %s", symbol, e)
        return None


def get_bond_quote(symbol: str) -> dict | None:
    """Current computed price for a savings-bond emission (plan 34.2).

    Takes the last 1-2 bars over a recent 30-day window — savings bonds move
    infrequently, so today alone may not yield a prev_close. Shaped like the
    equity quote (``last_price`` etc.) so portfoliost-instruments' existing
    ``toQuote`` translator reuses it unchanged. Returns ``None`` when the
    engine has no bar (unknown symbol / before issue date).
    """
    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=30)
    rows = get_bond_ohlcv(symbol, str(start), str(end))
    if not rows:
        return None
    latest = rows[-1]
    close = latest["close"]
    quote: dict = {
        "symbol": symbol,
        "last_price": close,
        "open": latest["open"],
        "high": latest["high"],
        "low": latest["low"],
        "currency": "PLN",
        "date": latest["date"],
    }
    if len(rows) >= 2:
        prev_close = rows[-2]["close"]
        change = round(close - prev_close, 4)
        quote["prev_close"] = prev_close
        quote["change"] = change
        quote["change_percent"] = round(change / prev_close, 4) if prev_close else None
    return quote


def _bond_profile_from_db(symbol: str) -> dict | None:
    """Read a bond emission's 10-column row from Postgres (D79 21.3).

    Returns ``None`` when the DB is unset, raises, or has no such symbol — the
    caller then falls back to the ``obligacje`` provider. Values are normalized
    through ``_plain`` so the DB-first path is wire-identical to the OpenBB path.
    """
    if not db.database_url():
        return None
    try:
        from openbb_obligacje import store as bond_store

        bond = bond_store.fetch_bond_series(symbol.strip().upper())
    except Exception as e:
        logger.warning("bond DB profile failed for %s: %s", symbol, e)
        return None
    if bond is None:
        return None
    return {
        "symbol": bond.symbol,
        "name": bond.name,
        "series_code": bond.series_code,
        "issue_date": _plain(bond.issue_date),
        "maturity_date": _plain(bond.maturity_date),
        "term_months": _plain(bond.term_months),
        "rate_rule": bond.rate_rule,
        "margin": _plain(bond.margin),
        "fee_b": _plain(bond.fee_b),
        "nominal": _plain(bond.nominal),
    }


def get_bond_profile(symbol: str) -> dict | None:
    """Issue parameters for a known savings-bond emission (D79 19.7).

    DB-first: reads ``openst.bond_series`` directly when Postgres is configured.
    Falls back to ``obb.equity.profile`` with ``provider="obligacje"`` when the
    DB yields nothing (import not yet run / DB-less / DB error).
    Returns ``None`` when the symbol is unknown.
    """
    row = _bond_profile_from_db(symbol)
    if row is not None:
        return row
    try:
        df = obb.equity.profile(symbol, provider="obligacje").to_df()
        if df.empty:
            return None
        records = _df_records(df)
        return records[0] if records else None
    except Exception as e:
        logger.warning("obligacje profile failed for %s: %s", symbol, e)
        return None


def get_corp_bond_profile(symbol: str) -> dict | None:
    """Profile metadata for a Catalyst corporate bond (D80 25.3).

    Routed through the ``biznesradar`` provider, whose
    ``EquityProfileFetcher.fetch_data`` dispatches Catalyst codes
    (three uppercase letters + four digits, e.g. ``BST0327``) to the
    obligacje.pl ``CorporateBondProfileFetcher`` and otherwise probes
    biznesradar (empty for bonds). Returns ``None`` when the bond is
    unknown.
    """
    try:
        df = obb.equity.profile(symbol, provider="biznesradar").to_df()
        if df.empty:
            return None
        records = _df_records(df)
        return records[0] if records else None
    except Exception as e:
        logger.warning("corp-bond profile failed for %s: %s", symbol, e)
        return None


def _bond_search_from_db(query: str) -> list[dict] | None:
    """Search savings-bond emissions in Postgres (D79 21.3).

    Matches every emission whose symbol starts with ``query`` or whose name
    contains it, and maps rows to the ``obligacje`` search shape
    (``{symbol, name, maturity_date}``). Returns ``None`` when the DB is unset
    or raises — the caller then falls back to the ``obligacje`` provider.
    """
    if not db.database_url():
        return None
    try:
        from openbb_obligacje import store as bond_store

        return [
            {
                "symbol": bond.symbol,
                "name": bond.name,
                "maturity_date": _plain(bond.maturity_date),
            }
            for bond in bond_store.search_bond_series(query.strip(), is_symbol=False)
        ]
    except Exception as e:
        logger.warning("bond DB search failed for '%s': %s", query, e)
        return None


def search_bonds(query: str) -> list[dict]:
    """Search savings-bond emissions by symbol prefix or name substring (D79 19.7).

    DB-first: reads ``openst.bond_series`` directly when Postgres is configured.
    Falls back to ``obb.equity.search`` with ``provider="obligacje"`` when the
    DB yields nothing (import not yet run / DB-less / DB error).
    Returns an empty list when there are no results.
    """
    rows = _bond_search_from_db(query)
    if rows:
        return rows
    try:
        df = obb.equity.search(query, provider="obligacje").to_df()
        if df.empty:
            return []
        records = _df_records(df)
        return records if records else []
    except Exception as e:
        logger.warning("obligacje search failed for '%s': %s", query, e)
        return []


def get_fundamentals(ticker: str, statement: str, period: str) -> dict | None:
    """Return ``{"provider": <name>, "rows": [...]}`` for the first provider that answered.

    §79.2 — the provider that satisfied the walk IS part of the answer. The
    three statements are three independent walks, so one instrument can answer
    with income from ``fmp`` and a balance sheet from ``yfinance``, in different
    currencies and units; the consumer merged them into one response with no
    record of which was which. Returning rows alone made that unrecoverable at
    every hop below, including through cachest's 24h body cache — so provenance
    has to travel in the body, not a header.

    Returns ``None`` when every provider failed or returned nothing; the route
    turns that into a 404, exactly as the previous empty-list return did.
    """
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
                return {"provider": provider, "rows": records}
            continue
        except Exception as e:
            if _classify(e, provider, ticker) is _Action.STOP:
                return None
            continue
    return None


def _merged_dividend_calendar(fn, start_date: str, end_date: str) -> list[dict]:
    """§52.6 — merge the dividend calendar across CALENDAR_PROVIDERS.

    The global dividend calendar is consumed per-symbol downstream (instruments
    ``toCalendar`` filters rows by symbol), so a first-non-empty provider
    strategy would mask GPW (biznesradar) rows whenever a US provider returns
    rows for the same window.  Merge instead, deduping on
    (symbol, ex_dividend_date, payment_date, amount).  Earnings keeps the
    first-non-empty strategy (its providers cover the same universe).
    """
    records: list[dict] = []
    seen: set = set()
    for provider in CALENDAR_PROVIDERS["dividend"]:
        if _provider_is_blocked(provider):
            continue
        try:
            df = fn(start_date=start_date, end_date=end_date, provider=provider).to_df()
        except Exception as e:
            # A merge must never abort: one throttled provider contributes nothing and
            # the remaining providers still surface their rows.
            _classify(e, provider, f"calendar/dividend {start_date}..{end_date}")
            continue
        if df.empty:
            continue
        for record in _df_records(df):
            key = (
                record.get("symbol"),
                str(record.get("ex_dividend_date")),
                str(record.get("payment_date")),
                record.get("amount"),
            )
            if key not in seen:
                seen.add(key)
                records.append(record)
    return records


def get_calendar(kind: str, start_date: str, end_date: str) -> list[dict]:
    fn = getattr(obb.equity.calendar, kind)
    if kind == "dividend":
        return _merged_dividend_calendar(fn, start_date, end_date)
    for provider in CALENDAR_PROVIDERS[kind]:
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
            if _classify(e, provider, kind) is _Action.STOP:
                return []
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
            _classify(e, provider, query)
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
            if _classify(e, p, ticker) is _Action.STOP:
                return []
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
            if _classify(e, provider, ticker) is _Action.STOP:
                return []
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
            if _classify(e, provider, ticker) is _Action.STOP:
                return []
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
            if _classify(e, provider, ticker) is _Action.STOP:
                return []
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
            if _classify(e, provider, ticker) is _Action.STOP:
                return None
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
            _classify(e, provider, ticker)
            continue

    domain = urlparse(website or "").hostname
    if not domain:
        return None
    return {"source": "favicon", "remote_url": _FAVICON_URL.format(domain=domain)}


# --- Polish fund categories (analizy.pl) — plan §72.39 step 2, stage 2 -------
#
# Why this exists: a PPO/PPI fund's broker executes against the *category* NAV
# (e.g. ING Akcji category W), while every other provider we carry serves the
# fund's default category only. Category W's series reproduces four of five
# stored executed prices to the cent, so the executed series is real and
# published — our chain simply had no route to it.
#
# The key is the provider's own category code, which is NOT derivable from a
# `.TFI` symbol: of ING01's nine categories only ING01/U/W/T/F resolve and
# A/I/K/S/E are 404. So callers pass the code (ING01W), never a guessed one.

ANALIZY_QUOTATION_URL = "https://www.analizy.pl/api/quotation/fio/{code}"
ANALIZY_TIMEOUT = 20
# Every fund category in this universe is PLN-denominated. The source states the
# currency on both the envelope and each series, so this is asserted rather than
# assumed — a bare number with no currency is the mistake ticker_reference's
# empty yahoo_suffix already caused once (plan §72.39 stage 2).
ANALIZY_EXPECTED_CURRENCY = "PLN"


class UnknownFundCategory(Exception):
    """The category code does not exist upstream (analizy.pl answered 404).

    Distinct from "no history in the requested window", which is a legitimate
    empty result. Collapsing the two is exactly the silent failure this provider
    exists to avoid: `200` with zero bars is what a *dead* provider looks like,
    and that shape is how a broken mapping once shipped unnoticed (reverted in
    77434fd). Keep this an error so the route can propagate a 404.
    """


def _select_analizy_series(payload: dict) -> dict | None:
    """Pick the non-empty price series from an analizy.pl quotation payload.

    Selects on *having points*, never on position: the payload carries a second
    `fund_with_dividend_*` series that is empty on every fund checked, and
    nothing documents the order as stable. Returns None when no series has data.
    """
    for series in payload.get("series") or []:
        if series.get("price"):
            return series
    return None


def _analizy_currency(payload: dict, series: dict | None) -> str | None:
    """Currency declared by the source, preferring the series' own value."""
    if series and series.get("currency"):
        return str(series["currency"]).upper()
    if payload.get("currency"):
        return str(payload["currency"]).upper()
    return None


def get_fund_category_history(
    code: str, start_date: str, end_date: str
) -> list[dict] | None:
    """NAV history for one Polish fund category, as [{"date", "close"}, ...].

    `code` is an analizy.pl category code (ING01W), upper-cased. Returns rows in
    ascending date order, or [] when the category exists but has no valuation in
    the window. Raises UnknownFundCategory when the code does not exist, so the
    caller can distinguish "no history" from "wrong code".
    """
    cat = (code or "").strip().upper()
    if not cat:
        raise UnknownFundCategory("empty fund category code")

    url = ANALIZY_QUOTATION_URL.format(code=cat)
    try:
        resp = httpx.get(
            url,
            timeout=ANALIZY_TIMEOUT,
            headers={
                "User-Agent": "portfoliost-openst/1.0",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
    except Exception as e:
        logger.warning("analizy.pl fetch failed for %s: %s", cat, e)
        return None

    if resp.status_code == 404:
        # {"success": false} — the code is not in this universe.
        raise UnknownFundCategory(f"no such fund category: {cat}")
    if resp.status_code != 200:
        logger.warning("analizy.pl %s for %s returned %s", resp.status_code, cat, url)
        return None

    try:
        payload = resp.json()
    except Exception as e:
        logger.warning("analizy.pl payload for %s is not JSON: %s", cat, e)
        return None

    series = _select_analizy_series(payload)
    currency = _analizy_currency(payload, series)
    if currency != ANALIZY_EXPECTED_CURRENCY:
        # Refuse rather than pass on a bare number: every category here is PLN,
        # so anything else means we are reading the wrong series or the source
        # changed shape.
        logger.warning(
            "analizy.pl %s declares currency %r, expected %r — refusing",
            cat,
            currency,
            ANALIZY_EXPECTED_CURRENCY,
        )
        return None

    if series is None:
        return []

    rows = []
    for point in series["price"]:
        date_str = point.get("date")
        close = _safe_float(point.get("value"))
        if not date_str or close is None:
            continue
        if start_date and date_str < start_date:
            continue
        if end_date and date_str > end_date:
            continue
        rows.append({"date": date_str, "close": close})

    rows.sort(key=lambda r: r["date"])
    _remember_symbol_currency(cat, currency)
    return rows
