# openst

OpenBB wrapper service. Exposes financial data via HTTP with 24h Redis cache.

## Endpoints

| Method | Path | Returns |
|--------|------|---------|
| GET | `/dividend/yield/{ticker}` | Current dividend yield as decimal string, e.g. `"2.45"` |
| GET | `/dividend/history/{ticker}` | Dividend payment history, e.g. `[{"date": "2024-03-15", "amount": "0.2500"}]` |

Returns `404` if no data found for the ticker.

## Run

```bash
cp .env.example .env   # fill in OPENBB_PAT
docker compose up --build
```

Service available at `http://localhost:8080`.

## Test

```bash
docker compose --profile test run --rm test
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENBB_PAT` | Yes | — | OpenBB personal access token |
| `REDIS_HOST` | No | `localhost` | Redis hostname |
| `REDIS_PORT` | No | `6379` | Redis port |
| `REDIS_PASSWORD` | No | `` | Redis password |
| `REDIS_DB` | No | `0` | Redis database index |
