# Graph Report - openst  (2026-09-15)

## Corpus Check
- 6 files · ~4,288 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 147 nodes · 295 edges · 15 communities (13 shown, 2 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c9fad2d3`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Redis Cache Layer|Redis Cache Layer]]
- [[_COMMUNITY_OpenBB Dividend Client|OpenBB Dividend Client]]
- [[_COMMUNITY_FastAPI Endpoints|FastAPI Endpoints]]
- [[_COMMUNITY_Dividend History Flow|Dividend History Flow]]
- [[_COMMUNITY_Package Init|Package Init]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]

## God Nodes (most connected - your core abstractions)
1. `_cached_or_404()` - 20 edges
2. `_is_rate_limited()` - 19 edges
3. `_block_provider()` - 19 edges
4. `_provider_is_blocked()` - 19 edges
5. `_is_invalid_ticker()` - 16 edges
6. `_plain()` - 15 edges
7. `_check_pays_dividend()` - 11 edges
8. `_safe_float()` - 11 edges
9. `_df_records()` - 11 edges
10. `get_company_news()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `dividend_yield()` --calls--> `get_dividend_yield()`  [EXTRACTED]
  main.py → openbb_client.py
- `price_history()` --calls--> `get_price_history()`  [EXTRACTED]
  main.py → openbb_client.py
- `dividend_history()` --calls--> `get_dividend_history()`  [EXTRACTED]
  main.py → openbb_client.py
- `equity_profile()` --calls--> `get_profile()`  [EXTRACTED]
  main.py → openbb_client.py
- `equity_quote()` --calls--> `get_quote()`  [EXTRACTED]
  main.py → openbb_client.py

## Communities (15 total, 2 thin omitted)

### Community 0 - "Redis Cache Layer"
Cohesion: 0.17
Nodes (35): _block_provider(), _df_records(), get_calendar(), get_crypto_ohlcv(), get_crypto_quote(), get_crypto_search(), get_dividend_history(), get_dividend_yield() (+27 more)

### Community 1 - "OpenBB Dividend Client"
Cohesion: 0.16
Nodes (16): _cached_or_404(), crypto_profile(), crypto_quote(), crypto_search(), equity_filings(), equity_fundamentals(), equity_institutional_ownership(), equity_logo() (+8 more)

### Community 2 - "FastAPI Endpoints"
Cohesion: 0.12
Nodes (19): get_company_news(), get_projections(), _news_source(), _plain(), Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive. (+11 more)

### Community 3 - "Dividend History Flow"
Cohesion: 0.17
Nodes (7): _JSONResponse, RedisCache, JSONResponse that serializes NaN/Inf floats as null instead of crashing., JSONResponse that serializes NaN/Inf floats as null instead of crashing., JSONResponse that serializes NaN/Inf floats as null instead of crashing., JSONResponse that serializes NaN/Inf floats as null instead of crashing., _SafeJSONResponse

### Community 4 - "Package Init"
Cohesion: 0.22
Nodes (9): _df_single_long_records(), get_mda(), Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only (+1 more)

### Community 5 - "Community 5"
Cohesion: 0.33
Nodes (8): database_url(), _ensure_journal(), get_conn(), migrate(), _pending(), Thin Postgres access for openst (D79 — retail savings bonds).  Reads ``DATABASE_, Open a plain psycopg2 connection. Requires ``DATABASE_URL`` to be set., Apply pending migrations from ``migrations/``, journaling each exactly once.

### Community 6 - "Community 6"
Cohesion: 0.25
Nodes (8): dividend_history(), dividend_yield(), price_history(), Serialize to JSON, replacing any NaN/Inf floats with null., Serialize to JSON, replacing any NaN/Inf floats with null., Serialize to JSON, replacing any NaN/Inf floats with null., Serialize to JSON, replacing any NaN/Inf floats with null., _safe_json_dumps()

### Community 7 - "Community 7"
Cohesion: 0.33
Nodes (6): _check_pays_dividend(), Return True if ticker has any dividend history across all providers., Return True if ticker has any dividend history across all providers., Return True if ticker has any dividend history across all providers., Return True if ticker has any dividend history across all providers., Return True if ticker has any dividend history across all providers.

### Community 8 - "Community 8"
Cohesion: 0.4
Nodes (5): get_logo(), Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im, Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im, Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im, Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im

### Community 9 - "Community 9"
Cohesion: 0.4
Nodes (5): get_insider_trading(), SEC Form 4 insider transactions (director/officer purchases & sales)., SEC Form 4 insider transactions (director/officer purchases & sales)., SEC Form 4 insider transactions (director/officer purchases & sales)., SEC Form 4 insider transactions (director/officer purchases & sales).

### Community 10 - "Community 10"
Cohesion: 0.5
Nodes (4): Return an int, or None for NaN/None/non-numeric values., Return an int, or None for NaN/None/non-numeric values., Return an int, or None for NaN/None/non-numeric values., _safe_int()

### Community 11 - "Community 11"
Cohesion: 0.5
Nodes (4): crypto_ohlcv(), _default_dates(), equity_calendar(), price_ohlcv()

### Community 12 - "Community 12"
Cohesion: 0.67
Nodes (3): lifespan(), Apply schema migrations at boot when a database is configured.      Guarded by `, _run_migrations()

## Knowledge Gaps
- **63 isolated node(s):** `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Round and return a float, or None for NaN/None/non-numeric values.`, `Return an int, or None for NaN/None/non-numeric values.`, `Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin` (+58 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_SafeJSONResponse` connect `Dividend History Flow` to `OpenBB Dividend Client`?**
  _High betweenness centrality (0.099) - this node is a cross-community bridge._
- **Why does `_plain()` connect `FastAPI Endpoints` to `Redis Cache Layer`, `Community 8`, `Community 10`, `Package Init`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Why does `_check_pays_dividend()` connect `Community 7` to `Redis Cache Layer`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **What connects `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Round and return a float, or None for NaN/None/non-numeric values.` to the rest of the system?**
  _63 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FastAPI Endpoints` be split into smaller, more focused modules?**
  _Cohesion score 0.12 - nodes in this community are weakly interconnected._