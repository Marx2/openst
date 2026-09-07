# openst

OpenBB wrapper service. Exposes financial data via HTTP with 24h Redis cache.

## Endpoints

| Method | Path | Returns |
|--------|------|---------|
| GET | `/dividend/yield/{ticker}` | Current dividend yield as decimal string, e.g. `"2.45"` |
| GET | `/dividend/history/{ticker}` | Dividend payment history, e.g. `[{"date": "2024-03-15", "amount": "0.2500"}]` |
| GET | `/price/history/{ticker}` | 1y close prices `[{"date": "...", "close": ...}]` |
| GET | `/price/ohlcv/{ticker}?start&end` | OHLCV rows (dates default to last 365 days) |
| GET | `/equity/profile/{ticker}` | Company profile |
| GET | `/equity/quote/{ticker}` | Latest quote |
| GET | `/equity/metrics/{ticker}` | Fundamental metrics incl. `dividend_yield` |
| GET | `/equity/projections/{ticker}` | Analyst estimates consensus + recommendation |
| GET | `/equity/fundamentals/{ticker}?statement=income&period=annual` | Statements: `income`/`balance`/`cash`, `annual`/`quarter` |
| GET | `/equity/calendar/{kind}?start&end` | `kind`: `earnings`/`dividend` |
| GET | `/equity/search/{query}` | Equity search |
| GET | `/equity/ownership/{ticker}` | SEC insider trading (Form 4) |
| GET | `/equity/ownership/institutional/{ticker}` | SEC institutional holdings (Form 13F) |
| GET | `/equity/filings/{ticker}` | SEC filing index (10-K, 10-Q, 8-K) |
| GET | `/equity/fundamentals/{ticker}/mda` | Management Discussion & Analysis from latest report |

Returns `404` if no data found for the ticker.

## Data Providers

Requests try providers in fallback order until one returns data:

| Endpoint group | Provider order | Needs key |
|----------------|----------------|-----------|
| Dividends | yfinance → fmp → intrinio → nasdaq | fmp, intrinio, nasdaq |
| Yield / metrics | yfinance → fmp → intrinio | fmp, intrinio |
| Price history / OHLCV | yfinance → fmp → intrinio → polygon → cboe → tiingo | fmp, intrinio, polygon, tiingo |
| Profile / quote | fmp → yfinance → cboe | fmp |
| Fundamentals | fmp → yfinance → polygon → sec | fmp, polygon |
| Projections | fmp → yfinance → tmx | fmp |
| Calendar | fmp | fmp |
| Search | sec → nasdaq → cboe | nasdaq |
| Ownership (insider) | sec | — |
| Ownership (institutional) | sec | — |
| Filings | sec | — |
| MD&A | sec | — |

A provider returning rate-limit/paywall errors is blocked in-process for 24h.
Keyless providers (`cboe`, `sec`, `tmx`, `yfinance`) need no configuration.

## Run

```bash
cp env.example .env   # fill in API keys
docker compose up --build
```

Service available at `http://localhost:8080`.

## Test

```bash
docker compose --profile test run --rm test
```

## Environment Variables

Credentials are read by OpenBB using the exact variable names below (or `~/.openbb_platform/user_settings.json`).

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FMP_API_KEY` | recommended | — | FMP — fundamentals, quotes, calendar |
| `INTRINIO_API_KEY` | No | — | Intrinio fallback (paid subscription needed) |
| `POLYGON_API_KEY` | No | — | Polygon — price history, statements, company news |
| `NASDAQ_API_KEY` | No | — | Nasdaq Data Link — dividend history, search, econ calendar |
| `TIINGO_TOKEN` | No | — | Tiingo — price history fallback (news API is paid tier) |
| `REDIS_HOST` | No | `localhost` | Redis hostname |
| `REDIS_PORT` | No | `6379` | Redis port |
| `REDIS_PASSWORD` | No | `` | Redis password |
| `REDIS_DB` | No | `0` | Redis database index |

## License