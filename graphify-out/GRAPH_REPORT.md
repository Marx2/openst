# Graph Report - openst  (2026-09-07)

## Corpus Check
- 4 files · ~2,841 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 76 nodes · 181 edges · 15 communities (12 shown, 3 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b4e10e2a`
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

## God Nodes (most connected - your core abstractions)
1. `_is_rate_limited()` - 15 edges
2. `_block_provider()` - 15 edges
3. `_provider_is_blocked()` - 15 edges
4. `_cached_or_404()` - 15 edges
5. `_is_invalid_ticker()` - 13 edges
6. `_plain()` - 10 edges
7. `_df_records()` - 10 edges
8. `_single_record()` - 10 edges
9. `_check_pays_dividend()` - 9 edges
10. `get_dividend_yield()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `dividend_yield()` --calls--> `get_dividend_yield()`  [EXTRACTED]
  main.py → openbb_client.py
- `_SafeJSONResponse` --uses--> `RedisCache`  [INFERRED]
  main.py → cache.py
- `price_history()` --calls--> `get_price_history()`  [EXTRACTED]
  main.py → openbb_client.py
- `dividend_history()` --calls--> `get_dividend_history()`  [EXTRACTED]
  main.py → openbb_client.py
- `equity_profile()` --calls--> `get_profile()`  [EXTRACTED]
  main.py → openbb_client.py

## Communities (15 total, 3 thin omitted)

### Community 0 - "Redis Cache Layer"
Cohesion: 0.22
Nodes (10): equity_logo(), _df_records(), _df_single_long_records(), get_logo(), _plain(), Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive. (+2 more)

### Community 1 - "OpenBB Dividend Client"
Cohesion: 0.22
Nodes (4): _JSONResponse, RedisCache, JSONResponse that serializes NaN/Inf floats as null instead of crashing., _SafeJSONResponse

### Community 2 - "FastAPI Endpoints"
Cohesion: 0.32
Nodes (4): _default_dates(), equity_calendar(), equity_filings(), price_ohlcv()

### Community 3 - "Dividend History Flow"
Cohesion: 0.43
Nodes (6): get_dividend_yield(), get_ohlcv_history(), Round and return a float, or None for NaN/None/non-numeric values., Return an int, or None for NaN/None/non-numeric values., _safe_float(), _safe_int()

### Community 4 - "Package Init"
Cohesion: 0.29
Nodes (7): equity_metrics(), equity_profile(), equity_projections(), get_metrics(), get_profile(), get_projections(), _single_record()

### Community 5 - "Community 5"
Cohesion: 0.47
Nodes (6): _block_provider(), get_fundamentals(), get_insider_trading(), _provider_is_blocked(), SEC Form 4 insider transactions (director/officer purchases & sales)., search_equities()

### Community 6 - "Community 6"
Cohesion: 0.33
Nodes (6): _cached_or_404(), equity_fundamentals(), equity_institutional_ownership(), equity_mda(), equity_ownership(), equity_search()

### Community 7 - "Community 7"
Cohesion: 0.4
Nodes (5): get_filings(), get_mda(), _is_rate_limited(), SEC EDGAR filing index (10-K, 10-Q, 8-K, etc.) with access URLs., Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only

### Community 8 - "Community 8"
Cohesion: 0.5
Nodes (4): _check_pays_dividend(), Return True if ticker has any dividend history across all providers., Return True if ticker has any dividend history across all providers., Return True if ticker has any dividend history across all providers.

### Community 9 - "Community 9"
Cohesion: 0.5
Nodes (4): get_calendar(), get_institutional_ownership(), _is_invalid_ticker(), SEC Form 13F institutional holdings (filed quarterly by $100M+ AUM managers).

### Community 10 - "Community 10"
Cohesion: 0.67
Nodes (3): dividend_yield(), Serialize to JSON, replacing any NaN/Inf floats with null., _safe_json_dumps()

## Knowledge Gaps
- **16 isolated node(s):** `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Round and return a float, or None for NaN/None/non-numeric values.`, `Return an int, or None for NaN/None/non-numeric values.`, `Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin` (+11 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_SafeJSONResponse` connect `OpenBB Dividend Client` to `FastAPI Endpoints`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Why does `_plain()` connect `Redis Cache Layer` to `Dividend History Flow`, `Package Init`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **What connects `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Round and return a float, or None for NaN/None/non-numeric values.` to the rest of the system?**
  _16 weakly-connected nodes found - possible documentation gaps or missing edges._