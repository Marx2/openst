# openst — Design Spec

**Date:** 2026-05-22

## Context

openst is a FastAPI service that wraps the openbb library to expose financial data via HTTP. It caches all responses in Redis for 24h to avoid repeated upstream calls. Built as a Docker image; tested via Docker Compose.

---

## Architecture

Minimal structure — no config.yaml abstraction. Endpoints defined directly in Python; cache logic explicit (get/set), not decorator-based.

```
openst/
├── main.py              # FastAPI app + route handlers
├── openbb_client.py     # openbb calls: dividend yield, dividend history
├── cache.py             # RedisCache: sync get/set, 24h SETEX TTL
├── requirements.txt
├── Dockerfile           # multi-stage: builder → test → runtime
├── docker-compose.yml   # redis + app + test (profile: test)
├── .env                 # secrets (git-ignored)
├── readme.md
└── tests/
    ├── test_main.py
    ├── test_cache.py
    └── test_openbb_client.py
```

---

## Endpoints

### `GET /dividend/yield/{ticker}`
Returns current dividend yield as a decimal string.

**Response:** `200 OK` — plain string, e.g. `"2.45"`

### `GET /dividend/history/{ticker}`
Returns full dividend payment history as JSON array.

**Response:** `200 OK` — JSON array, e.g.:
```json
[{"date": "2024-03-15", "amount": "0.25"}, ...]
```

Both endpoints return `404` if openbb returns no data, `502` if all providers fail.

---

## Cache

- **Backend:** Redis via `redis` (sync client, `decode_responses=True`)
- **TTL:** 86400s (24h), enforced by Redis `SETEX` — expired = miss, no stale fallback
- **Keys:** `dividend_yield:{ticker}`, `dividend_history:{ticker}`
- **Value:** JSON string

`cache.py` interface:
```python
class RedisCache:
    def get(self, key: str) -> str | None      # None if missing/expired
    def set(self, key: str, value: str, ttl: int = 86400) -> None
```

---

## openbb Client

`openbb_client.py` — pure functions, no FastAPI dependency.

Provider fallback (yfinance → fmp) with broad `except Exception` per backtest pattern:

```python
def get_dividend_yield(ticker: str) -> str | None:
    for provider in ["yfinance", "fmp"]:
        try:
            df = obb.equity.fundamental.metrics(ticker, provider=provider).to_df()
            if df.empty: continue
            return str(Decimal(str(df.iloc[0]["dividend_yield"])).quantize(Decimal("0.01")))
        except Exception:
            continue
    return None

def get_dividend_history(ticker: str) -> list[dict] | None:
    for provider in ["yfinance", "fmp"]:
        try:
            df = obb.equity.fundamental.dividends(ticker, provider=provider).to_df()
            if df.empty: continue
            return [{"date": str(row.name.date()), "amount": str(Decimal(str(row["amount"])).quantize(Decimal("0.0001")))} for _, row in df.iterrows()]
        except Exception:
            continue
    return None
```

---

## Secrets & Config

All via `.env` + `load_dotenv()`:

```
OPENBB_PAT=...
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
```

openbb picks up `OPENBB_PAT` automatically on import.

---

## Docker

**Dockerfile** — three stages:
1. `builder` — installs dependencies
2. `test` — copies source + tests, runs pytest
3. `runtime` — copies source, runs uvicorn on port 8080

**docker-compose.yml:**
- `redis` — `redis:7-alpine`, healthcheck on `redis-cli ping`
- `app` — builds `runtime` target, port 8080, depends on redis healthy, `env_file: .env`
- `test` — builds `test` target, profile `test`, depends on redis healthy

Run tests: `docker compose --profile test run --rm test`

---

## Tests

- `pytest` + `pytest-asyncio`, `httpx` test client
- openbb calls mocked via `unittest.mock.patch`
- Redis uses real test container (no mocks)
- Coverage: cache hit/miss, provider fallback, 404/502 responses

---

## readme.md

Concise: what it is, endpoints, how to run, how to test, env vars table.
