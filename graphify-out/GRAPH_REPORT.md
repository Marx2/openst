# Graph Report - openst  (2026-09-08)

## Corpus Check
- 4 files · ~3,188 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 95 nodes · 210 edges · 13 communities
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `074e2b88`
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

## God Nodes (most connected - your core abstractions)
1. `_is_rate_limited()` - 16 edges
2. `_block_provider()` - 16 edges
3. `_provider_is_blocked()` - 16 edges
4. `_cached_or_404()` - 16 edges
5. `_is_invalid_ticker()` - 14 edges
6. `_plain()` - 14 edges
7. `_check_pays_dividend()` - 10 edges
8. `_df_records()` - 10 edges
9. `_single_record()` - 10 edges
10. `get_company_news()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `equity_profile()` --calls--> `get_profile()`  [EXTRACTED]
  main.py → openbb_client.py
- `equity_quote()` --calls--> `get_quote()`  [EXTRACTED]
  main.py → openbb_client.py
- `equity_metrics()` --calls--> `get_metrics()`  [EXTRACTED]
  main.py → openbb_client.py
- `equity_projections()` --calls--> `get_projections()`  [EXTRACTED]
  main.py → openbb_client.py
- `equity_logo()` --calls--> `get_logo()`  [EXTRACTED]
  main.py → openbb_client.py

## Communities (13 total, 0 thin omitted)

### Community 0 - "Redis Cache Layer"
Cohesion: 0.16
Nodes (20): _df_records(), _df_single_long_records(), get_company_news(), get_metrics(), get_profile(), get_projections(), get_quote(), _news_source() (+12 more)

### Community 1 - "OpenBB Dividend Client"
Cohesion: 0.18
Nodes (16): _cached_or_404(), _default_dates(), equity_calendar(), equity_filings(), equity_fundamentals(), equity_institutional_ownership(), equity_logo(), equity_mda() (+8 more)

### Community 2 - "FastAPI Endpoints"
Cohesion: 0.2
Nodes (10): dividend_yield(), Serialize to JSON, replacing any NaN/Inf floats with null., Serialize to JSON, replacing any NaN/Inf floats with null., _safe_json_dumps(), _check_pays_dividend(), get_dividend_yield(), Return True if ticker has any dividend history across all providers., Return True if ticker has any dividend history across all providers. (+2 more)

### Community 3 - "Dividend History Flow"
Cohesion: 0.2
Nodes (5): _JSONResponse, RedisCache, JSONResponse that serializes NaN/Inf floats as null instead of crashing., JSONResponse that serializes NaN/Inf floats as null instead of crashing., _SafeJSONResponse

### Community 4 - "Package Init"
Cohesion: 0.29
Nodes (7): get_ohlcv_history(), Round and return a float, or None for NaN/None/non-numeric values., Round and return a float, or None for NaN/None/non-numeric values., Return an int, or None for NaN/None/non-numeric values., Return an int, or None for NaN/None/non-numeric values., _safe_float(), _safe_int()

### Community 5 - "Community 5"
Cohesion: 0.47
Nodes (6): dividend_history(), _block_provider(), get_calendar(), get_dividend_history(), _is_rate_limited(), search_equities()

### Community 6 - "Community 6"
Cohesion: 0.5
Nodes (5): price_history(), get_fundamentals(), get_price_history(), _is_invalid_ticker(), _provider_is_blocked()

### Community 7 - "Community 7"
Cohesion: 0.67
Nodes (3): get_institutional_ownership(), SEC Form 13F institutional holdings (filed quarterly by $100M+ AUM managers)., SEC Form 13F institutional holdings (filed quarterly by $100M+ AUM managers).

### Community 8 - "Community 8"
Cohesion: 0.67
Nodes (3): get_filings(), SEC EDGAR filing index (10-K, 10-Q, 8-K, etc.) with access URLs., SEC EDGAR filing index (10-K, 10-Q, 8-K, etc.) with access URLs.

### Community 9 - "Community 9"
Cohesion: 0.67
Nodes (3): get_logo(), Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im, Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im

### Community 10 - "Community 10"
Cohesion: 0.67
Nodes (3): get_mda(), Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only

### Community 11 - "Community 11"
Cohesion: 0.67
Nodes (3): get_insider_trading(), SEC Form 4 insider transactions (director/officer purchases & sales)., SEC Form 4 insider transactions (director/officer purchases & sales).

## Knowledge Gaps
- **31 isolated node(s):** `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Round and return a float, or None for NaN/None/non-numeric values.`, `Return an int, or None for NaN/None/non-numeric values.`, `Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin` (+26 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_SafeJSONResponse` connect `Dividend History Flow` to `OpenBB Dividend Client`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **Why does `_plain()` connect `Redis Cache Layer` to `Community 9`, `Package Init`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Why does `_check_pays_dividend()` connect `FastAPI Endpoints` to `Redis Cache Layer`, `Community 5`, `Community 6`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **What connects `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Round and return a float, or None for NaN/None/non-numeric values.` to the rest of the system?**
  _31 weakly-connected nodes found - possible documentation gaps or missing edges._