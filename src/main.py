import base64
import json
import logging
import os
import time

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response

logger = logging.getLogger("openst")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
    logger.addHandler(_handler)

from .cache import RedisCache
from .openbb_client import (
    CALENDAR_KINDS,
    PERIODS,
    STATEMENTS,
    get_calendar,
    get_dividend_history,
    get_dividend_yield,
    get_fundamentals,
    get_logo,
    get_metrics,
    get_ohlcv_history,
    get_price_history,
    get_profile,
    get_projections,
    get_quote,
    search_equities,
)

import re as _re
from fastapi.responses import JSONResponse as _JSONResponse


class _SafeJSONResponse(_JSONResponse):
    """JSONResponse that serializes NaN/Inf floats as null instead of crashing."""

    def render(self, content) -> bytes:
        raw = json.dumps(content, ensure_ascii=False, allow_nan=True)
        raw = _re.sub(r'\bNaN\b', 'null', raw)
        raw = _re.sub(r'\bInfinity\b', 'null', raw)
        raw = _re.sub(r'\b-Infinity\b', 'null', raw)
        return raw.encode("utf-8")


app = FastAPI(default_response_class=_SafeJSONResponse)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000

    body_chunks = []
    async for chunk in response.body_iterator:
        body_chunks.append(chunk)
    body = b"".join(body_chunks)

    try:
        body_str = json.loads(body)
    except Exception:
        body_str = body.decode(errors="replace")

    try:
        log_body = json.dumps(body_str, ensure_ascii=False)
    except (ValueError, TypeError):
        log_body = repr(body_str)

    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code} ({elapsed:.1f}ms) {log_body}"
    )

    return Response(
        content=body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
    )


_FAVICON = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAbklEQVR4nI2SwQ3AIAwD"
    "eTNO58yI7EJbggxKnEDkRwU+W0BLYdPbr9tR95nR7WmVoZxZwbIpYoy1PfVTxsCtVghM"
    "GG+AyZiSxE1KEE/dpCSPJyXH+L2EAP5aORCaxjc79/0t+Wcm8o/NfyRZ65gXP1AKlpa+"
    "AnUAAAAASUVORK5CYII="
)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(_FAVICON, media_type="image/png")

_cache = RedisCache(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    password=os.environ.get("REDIS_PASSWORD") or None,
    db=int(os.environ.get("REDIS_DB", 0)),
)


@app.get("/dividend/yield/{ticker}")
def dividend_yield(ticker: str):
    key = f"dividend_yield:{ticker}"
    cached = _cache.get(key)
    if cached is not None:
        return json.loads(cached)

    value = get_dividend_yield(ticker)
    if value is None:
        raise HTTPException(status_code=404, detail=f"No dividend yield data for {ticker}")

    _cache.set(key, _safe_json_dumps(value))
    return value


@app.get("/price/history/{ticker}")
def price_history(ticker: str):
    from datetime import date, timedelta
    end = date.today()
    start = end - timedelta(days=365)
    key = f"price_history:{ticker}:{start}:{end}"
    cached = _cache.get(key)
    if cached is not None:
        return json.loads(cached)

    value = get_price_history(ticker, str(start), str(end))
    if value is None:
        raise HTTPException(status_code=404, detail=f"No price history for {ticker}")

    _cache.set(key, _safe_json_dumps(value))
    return value


@app.get("/dividend/history/{ticker}")
def dividend_history(ticker: str):
    key = f"dividend_history:{ticker}"
    cached = _cache.get(key)
    if cached is not None:
        return json.loads(cached)

    value = get_dividend_history(ticker)
    if value is None:
        raise HTTPException(status_code=404, detail=f"No dividend history data for {ticker}")

    _cache.set(key, _safe_json_dumps(value))
    return value


def _safe_json_dumps(value) -> str:
    """Serialize to JSON, replacing any NaN/Inf floats with null."""
    import math

    def default_handler(obj):
        return str(obj)

    # json.dumps with allow_nan=False would raise; instead we pre-sanitize
    # via a custom walk — but that's expensive. Simpler: use allow_nan=True
    # to produce non-spec output, then fix it, OR use a replacer approach.
    # Fastest: serialize with allow_nan=True and post-process the string.
    raw = json.dumps(value, ensure_ascii=False, allow_nan=True, default=default_handler)
    # Replace bare NaN / Infinity / -Infinity tokens (not inside strings)
    import re
    raw = re.sub(r'\bNaN\b', 'null', raw)
    raw = re.sub(r'\bInfinity\b', 'null', raw)
    raw = re.sub(r'\b-Infinity\b', 'null', raw)
    return raw


def _cached_or_404(key: str, fetch, not_found_msg: str):
    cached = _cache.get(key)
    if cached is not None:
        return json.loads(cached)

    value = fetch()
    if value is None:
        raise HTTPException(status_code=404, detail=not_found_msg)

    _cache.set(key, _safe_json_dumps(value))
    return value


def _default_dates():
    from datetime import date, timedelta
    end = date.today()
    start = end - timedelta(days=365)
    return str(start), str(end)


@app.get("/equity/profile/{ticker}")
def equity_profile(ticker: str):
    return _cached_or_404(
        f"equity_profile:{ticker}",
        lambda: get_profile(ticker),
        f"No profile data for {ticker}",
    )


@app.get("/equity/quote/{ticker}")
def equity_quote(ticker: str):
    return _cached_or_404(
        f"equity_quote:{ticker}",
        lambda: get_quote(ticker),
        f"No quote data for {ticker}",
    )


@app.get("/equity/metrics/{ticker}")
def equity_metrics(ticker: str):
    return _cached_or_404(
        f"equity_metrics:{ticker}",
        lambda: get_metrics(ticker),
        f"No fundamental metrics for {ticker}",
    )


@app.get("/equity/projections/{ticker}")
def equity_projections(ticker: str):
    return _cached_or_404(
        f"equity_projections:{ticker}",
        lambda: get_projections(ticker),
        f"No projections data for {ticker}",
    )


@app.get("/price/ohlcv/{ticker}")
def price_ohlcv(
    ticker: str,
    start: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    if start is None or end is None:
        default_start, default_end = _default_dates()
        start = start or default_start
        end = end or default_end

    def fetch():
        rows = get_ohlcv_history(ticker, start, end)
        return rows  # [] (invalid ticker) and None (all providers failed) both pass through

    return _cached_or_404(
        f"price_ohlcv:{ticker}:{start}:{end}",
        fetch,
        f"No OHLCV history for {ticker}",
    )


@app.get("/equity/fundamentals/{ticker}")
def equity_fundamentals(
    ticker: str,
    statement: str = Query(default="income", pattern=f"^({'|'.join(STATEMENTS)})$"),
    period: str = Query(default="annual", pattern=f"^({'|'.join(PERIODS)})$"),
):

    def fetch():
        records = get_fundamentals(ticker, statement, period)
        return records or None

    return _cached_or_404(
        f"fundamentals:{ticker}:{statement}:{period}",
        fetch,
        f"No {statement} statements for {ticker}",
    )


@app.get("/equity/calendar/{kind}")
def equity_calendar(
    kind: str,
    start: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    if kind not in CALENDAR_KINDS:
        raise HTTPException(status_code=404, detail=f"Unknown calendar kind {kind}")

    if start is None or end is None:
        default_start, default_end = _default_dates()
        start = start or default_start
        end = end or default_end

    def fetch():
        records = get_calendar(kind, start, end)
        return records or None

    return _cached_or_404(
        f"calendar:{kind}:{start}:{end}",
        fetch,
        f"No {kind} calendar entries in window",
    )


@app.get("/equity/search/{query}")
def equity_search(query: str):
    normalized = query.strip().lower()

    def fetch():
        records = search_equities(normalized)
        return records or None

    return _cached_or_404(
        f"equity_search:{normalized}",
        fetch,
        f"No search results for '{query}'",
    )


@app.get("/equity/logo/{ticker}")
def equity_logo(ticker: str):
    return _cached_or_404(
        f"equity_logo:{ticker.upper()}",
        lambda: get_logo(ticker),
        f"No logo resolvable for {ticker}",
    )
