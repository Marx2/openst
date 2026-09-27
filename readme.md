# openst

OpenBB wrapper service. Exposes financial data over HTTP with a Redis cache, plus
in-process provider fallback, a negative cache and a bound on concurrent upstream
walks.

## Endpoints

`{ticker}` is a symbol (equity ticker, fund code, or bond symbol). `?start`/`?end`
default to the trailing year; both must be `YYYY-MM-DD` or the request is `422`.

| Path | Returns |
|------|---------|
| `/dividend/yield/{ticker}` | Dividend yield, e.g. `2.45` |
| `/dividend/history/{ticker}` | `[{"date","amount","payment_date"?}]` |
| `/price/history/{ticker}` | Trailing-year closes `[{"date","close"}]` |
| `/price/ohlcv/{ticker}?start&end` | OHLCV rows |
| `/equity/profile/{ticker}` | Company profile |
| `/equity/quote/{ticker}` | Latest quote |
| `/equity/metrics/{ticker}` | Fundamental metrics incl. `dividend_yield` |
| `/equity/projections/{ticker}` | Analyst consensus + recommendation |
| `/equity/fundamentals/{ticker}?statement&period` | `statement`: `income`/`balance`/`cash`; `period`: `annual`/`quarter` |
| `/equity/calendar/{kind}?start&end` | `kind`: `earnings`/`dividend` |
| `/equity/search/{query}` | Equity search |
| `/equity/ownership/{ticker}` | SEC insider trading (Form 4) |
| `/equity/ownership/institutional/{ticker}` | SEC institutional holdings (Form 13F) |
| `/equity/filings/{ticker}` | SEC filing index |
| `/equity/fundamentals/{ticker}/mda` | Management Discussion & Analysis |
| `/equity/logo/{ticker}` | `{"source","remote_url"}` — the caller downloads the bytes |
| `/news/company/{ticker}?limit&start_date&end_date&provider` | `[{"date","title","text","url","symbols","source"}]` |
| `/crypto/ohlcv/{pair}?start&end` | Crypto OHLCV |
| `/crypto/quote/{pair}` | Latest crypto quote (last two bars of a 30-day window) |
| `/crypto/search/{query}` | Crypto search |
| `/crypto/profile/{pair}` | `{"symbol","currency","price","date"}` — derived from the quote |
| `/fixedincome/ohlcv/{symbol}?start&end` | Savings-bond priced redemption series |
| `/fixedincome/quote/{symbol}` | Computed bond price + prev_close |
| `/fixedincome/profile/{symbol}` | Issue parameters |
| `/fixedincome/search/{query}` | Bond search by symbol prefix or name |
| `/corp-bond/profile/{symbol}` | Catalyst corporate-bond metadata |
| `/corp-bond/catalogue` | Full listed bond catalogue as tickerref CSV (`text/csv`) |

Operational:

| Path | Purpose |
|------|---------|
| `/health` | Liveness. Does **not** check Redis or the database. |
| `/ready` | Readiness. `503` when Redis is unreachable. |
| `/__meta` | Service name and `APP_VERSION`. |
| `/metrics` | Prometheus text format. |

### Status codes

| Code | Meaning |
|------|---------|
| `404` | No data for this symbol. Negative-cached for 6 h, so a dead symbol costs one provider walk, not one per request. |
| `422` | A query parameter is missing or malformed. |
| `500` | A defect in this service — a provider walk is written to absorb provider errors, so a 500 means a bug here. |

A Redis outage does **not** fail requests: the cache degrades to misses and the pod
reports `503` on `/ready` so it leaves the load-balancer rotation.

## Data providers

Requests try providers in order until one returns data.

| Endpoint group | Provider order |
|----------------|----------------|
| Dividend history | nasdaq → yfinance → fmp → intrinio → dividendmax |
| Yield / metrics | yfinance → fmp → intrinio |
| Price history / OHLCV | yfinance → fmp → intrinio → polygon → cboe → tiingo → biznesradar |
| Profile | fmp → yfinance → biznesradar |
| Quote | fmp → yfinance → cboe → biznesradar |
| Statements | fmp → yfinance → polygon → sec |
| Projections | fmp → yfinance → tmx |
| Calendar — dividend | fmp + nasdaq + biznesradar, **merged** (see below) |
| Calendar — earnings | fmp → nasdaq → tmx |
| Equity search | sec → nasdaq → cboe → biznesradar |
| Company news | polygon → fmp → yfinance |
| Crypto OHLCV / quote | yfinance → fmp → tiingo |
| Crypto search | fmp |
| Ownership, filings, MD&A | sec |

The dividend calendar merges all three providers rather than taking the first
non-empty one: it is consumed per-symbol downstream, so a first-non-empty
strategy would hide GPW (biznesradar) rows whenever a US provider returned rows
for the same window. Earnings keeps first-non-empty, since its providers cover the
same universe.

Failure handling, in one place (`_classify`):

- a **throttle** (HTTP 402, rate limit, premium/paywall wording) blocks that
  provider **in-process for 24 h** and moves to the next one;
- an **unknown symbol** stops the walk, and the route's own "no data" value is
  returned (`[]` on some routes, `404` on others — that difference is deliberate);
- anything else is logged and the next provider is tried.

Keyless providers (`cboe`, `sec`, `tmx`, `yfinance`, `nasdaq`, `dividendmax`,
`biznesradar`, `obligacje`) need no configuration. Crypto `fmp`/`tiingo` are only
tried when their key is set.

### Provider plugins

Three OpenBB provider plugins live in `plugins/` and are installed into the image:

| Plugin | Covers |
|--------|--------|
| `openbb_biznesradar` | GPW equities, funds, savings bonds, Catalyst corporate bonds, dividend calendar |
| `openbb_obligacje` | obligacje.pl savings-bond engine (priced redemption series) |
| `openbb_dividendmax` | Public-page dividend history |

Each has its own test suite, run as a separate pytest invocation — a combined run
collides on the `tests` package name (both trees have `__init__.py`).

## Resilience

- **Negative cache** (plan §37.3) — a `None` fetch result is remembered for 6 h, so
  a delisted or unknown symbol does not re-run the full provider walk every request.
- **In-flight bound** (plan §37.4) — at most `UPSTREAM_MAX_INFLIGHT` (default 8)
  provider walks run concurrently. A walk takes 2–15 s; unbounded, a burst piled up
  dozens of long walks and OOM'd the pod (incident 2026-09-20). Every route is
  covered, including the three dividend/price routes that originally bypassed it.
- **Cache degradation** — Redis errors are contained, so a Redis outage costs speed
  and upstream quota, not availability.
- **Fund start clamping** (plan §45.5) — a fund's `start` is clamped to its oldest
  NAV date, so pre-inception pages are not scraped.
- **GBX normalization** (plan §63.5) — yfinance quotes LSE (`.L`) symbols in pence;
  those are divided by 100 so the rest of the system sees GBP.

## Run

```bash
cp env.example .env   # fill in API keys
docker compose up --build
```

Service on `http://localhost:8080`.

## Test

The suite needs Redis and Postgres, so it always runs through compose — never bare
`pytest`. The image must be rebuilt for source changes; `docker compose run` does
not rebuild on its own.

```bash
docker compose --profile test build test
docker compose --profile test run --rm test
```

542 tests: 364 in `tests/`, plus a suite per provider plugin. Five live-network
tests are marked `integration` and deselected by default
(`pytest.ini` → `addopts = -m "not integration"`). The same command runs in CI on
every push and pull request.

## Environment Variables

Credentials are read by OpenBB using these exact names (or
`~/.openbb_platform/user_settings.json`).

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FMP_API_KEY` | recommended | — | FMP — fundamentals, quotes, calendar, crypto |
| `INTRINIO_API_KEY` | No | — | Intrinio fallback (paid subscription needed) |
| `POLYGON_API_KEY` | No | — | Polygon — price history, statements, company news |
| `NASDAQ_API_KEY` | No | — | Nasdaq Data Link — dividends, search |
| `TIINGO_TOKEN` | No | — | Tiingo — price history and crypto |
| `REDIS_HOST` | No | `localhost` | Redis hostname |
| `REDIS_PORT` | No | `6379` | Redis port |
| `REDIS_PASSWORD` | No | — | Redis password |
| `REDIS_DB` | No | `0` | Redis database index |
| `DATABASE_URL` | No | unset | Postgres for bond series. Absent ⇒ bond routes fall back to their provider. |
| `UPSTREAM_MAX_INFLIGHT` | No | `8` | Concurrent provider walks |
| `APP_VERSION` | No | `0.0.0-dev` | Injected by CI; surfaced on `/__meta` and in metrics |
| `BIZNESRADAR_FETCH_DELAY_S` | No | provider default | Throttle between biznesradar scrapes |

## Layout

| Path | Role |
|------|------|
| `src/main.py` | Routes, caching, negative cache, in-flight bound |
| `src/openbb_client.py` | Provider walks and the shared error policy |
| `src/jsonio.py` | JSON serialization that never emits invalid JSON |
| `src/cache.py` | The only module that talks to Redis |
| `src/db.py` | Postgres access and the boot-time migration runner |
| `src/otel.py` | Metrics and tracing |
| `src/importers/` | Bond series, corp-bond catalogue, CPI importers |
| `migrations/` | Applied once, journaled in `openst.schema_migrations` |
| `plugins/` | OpenBB provider plugins, each with its own tests |
