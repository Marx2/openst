# Graph Report - openst  (2026-09-15)

## Corpus Check
- 5 files · ~3,821 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 121 nodes · 260 edges · 16 communities (15 shown, 1 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f18a4df2`
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
1. `_is_rate_limited()` - 19 edges
2. `_block_provider()` - 19 edges
3. `_provider_is_blocked()` - 19 edges
4. `_cached_or_404()` - 18 edges
5. `_is_invalid_ticker()` - 16 edges
6. `_plain()` - 15 edges
7. `_check_pays_dividend()` - 11 edges
8. `_safe_float()` - 11 edges
9. `_df_records()` - 11 edges
10. `_single_record()` - 10 edges

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

## Communities (16 total, 1 thin omitted)

### Community 0 - "Redis Cache Layer"
Cohesion: 0.11
Nodes (20): get_company_news(), get_projections(), _news_source(), _plain(), Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive. (+12 more)

### Community 1 - "OpenBB Dividend Client"
Cohesion: 0.18
Nodes (14): _cached_or_404(), crypto_quote(), equity_filings(), equity_fundamentals(), equity_institutional_ownership(), equity_logo(), equity_mda(), equity_metrics() (+6 more)

### Community 2 - "FastAPI Endpoints"
Cohesion: 0.26
Nodes (14): _block_provider(), get_crypto_ohlcv(), get_crypto_quote(), get_dividend_history(), get_dividend_yield(), get_ohlcv_history(), get_price_history(), _is_invalid_ticker() (+6 more)

### Community 3 - "Dividend History Flow"
Cohesion: 0.18
Nodes (6): _JSONResponse, RedisCache, JSONResponse that serializes NaN/Inf floats as null instead of crashing., JSONResponse that serializes NaN/Inf floats as null instead of crashing., JSONResponse that serializes NaN/Inf floats as null instead of crashing., _SafeJSONResponse

### Community 4 - "Package Init"
Cohesion: 0.25
Nodes (8): _df_single_long_records(), get_mda(), Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only

### Community 5 - "Community 5"
Cohesion: 0.57
Nodes (7): _df_records(), get_calendar(), get_crypto_search(), get_fundamentals(), _is_rate_limited(), _provider_is_blocked(), search_equities()

### Community 6 - "Community 6"
Cohesion: 0.29
Nodes (7): dividend_history(), dividend_yield(), price_history(), Serialize to JSON, replacing any NaN/Inf floats with null., Serialize to JSON, replacing any NaN/Inf floats with null., Serialize to JSON, replacing any NaN/Inf floats with null., _safe_json_dumps()

### Community 7 - "Community 7"
Cohesion: 0.33
Nodes (6): _check_pays_dividend(), Return True if ticker has any dividend history across all providers., Return True if ticker has any dividend history across all providers., Return True if ticker has any dividend history across all providers., Return True if ticker has any dividend history across all providers., Return True if ticker has any dividend history across all providers.

### Community 8 - "Community 8"
Cohesion: 0.7
Nodes (4): get_metrics(), get_profile(), get_quote(), _single_record()

### Community 9 - "Community 9"
Cohesion: 0.5
Nodes (4): get_insider_trading(), SEC Form 4 insider transactions (director/officer purchases & sales)., SEC Form 4 insider transactions (director/officer purchases & sales)., SEC Form 4 insider transactions (director/officer purchases & sales).

### Community 10 - "Community 10"
Cohesion: 0.5
Nodes (4): get_filings(), SEC EDGAR filing index (10-K, 10-Q, 8-K, etc.) with access URLs., SEC EDGAR filing index (10-K, 10-Q, 8-K, etc.) with access URLs., SEC EDGAR filing index (10-K, 10-Q, 8-K, etc.) with access URLs.

### Community 11 - "Community 11"
Cohesion: 0.5
Nodes (4): get_institutional_ownership(), SEC Form 13F institutional holdings (filed quarterly by $100M+ AUM managers)., SEC Form 13F institutional holdings (filed quarterly by $100M+ AUM managers)., SEC Form 13F institutional holdings (filed quarterly by $100M+ AUM managers).

### Community 12 - "Community 12"
Cohesion: 0.5
Nodes (4): get_logo(), Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im, Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im, Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im

### Community 13 - "Community 13"
Cohesion: 0.5
Nodes (4): crypto_ohlcv(), _default_dates(), equity_calendar(), price_ohlcv()

## Knowledge Gaps
- **48 isolated node(s):** `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Round and return a float, or None for NaN/None/non-numeric values.`, `Return an int, or None for NaN/None/non-numeric values.`, `Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin` (+43 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_SafeJSONResponse` connect `Dividend History Flow` to `OpenBB Dividend Client`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Why does `_plain()` connect `Redis Cache Layer` to `FastAPI Endpoints`, `Package Init`, `Community 5`, `Community 8`, `Community 12`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Why does `_check_pays_dividend()` connect `Community 7` to `Community 8`, `FastAPI Endpoints`, `Community 5`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **What connects `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Round and return a float, or None for NaN/None/non-numeric values.` to the rest of the system?**
  _48 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Redis Cache Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.11 - nodes in this community are weakly interconnected._