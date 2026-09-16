# Graph Report - openst  (2026-09-16)

## Corpus Check
- 9 files · ~6,494 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 202 nodes · 374 edges · 10 communities
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.65)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `aef5cd3d`
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

## God Nodes (most connected - your core abstractions)
1. `_cached_or_404()` - 20 edges
2. `_is_rate_limited()` - 19 edges
3. `_block_provider()` - 19 edges
4. `_provider_is_blocked()` - 19 edges
5. `_is_invalid_ticker()` - 16 edges
6. `_plain()` - 15 edges
7. `parse_emission()` - 12 edges
8. `_check_pays_dividend()` - 11 edges
9. `_safe_float()` - 11 edges
10. `_df_records()` - 11 edges

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

## Communities (10 total, 0 thin omitted)

### Community 0 - "Redis Cache Layer"
Cohesion: 0.11
Nodes (48): _block_provider(), _check_pays_dividend(), _df_records(), get_calendar(), get_crypto_ohlcv(), get_crypto_profile(), get_crypto_quote(), get_crypto_search() (+40 more)

### Community 1 - "OpenBB Dividend Client"
Cohesion: 0.08
Nodes (34): _cached_or_404(), crypto_ohlcv(), crypto_profile(), crypto_quote(), crypto_search(), _default_dates(), dividend_history(), dividend_yield() (+26 more)

### Community 2 - "FastAPI Endpoints"
Cohesion: 0.08
Nodes (36): add_months(), BondFetchError, _classify_rate(), _dec(), _extract_fee(), _extract_margin(), fetch_page(), main() (+28 more)

### Community 3 - "Dividend History Flow"
Cohesion: 0.09
Nodes (23): get_company_news(), get_projections(), _news_source(), _plain(), Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive. (+15 more)

### Community 4 - "Package Init"
Cohesion: 0.19
Nodes (14): build_url(), CpiFetchError, fetch_cpi(), main(), parse_cpi_rows(), CPI importer (D79 19.3) — obligacje.pl 12m inflation -> openst.cpi_12m.  Data so, Fetch (+ possibly insert) CPI data for a mode; returns a summary dict., Raised when obligacje.pl returns a non-200 or a page with no CPI rows. (+6 more)

### Community 5 - "Community 5"
Cohesion: 0.17
Nodes (7): _JSONResponse, RedisCache, JSONResponse that serializes NaN/Inf floats as null instead of crashing., JSONResponse that serializes NaN/Inf floats as null instead of crashing., JSONResponse that serializes NaN/Inf floats as null instead of crashing., JSONResponse that serializes NaN/Inf floats as null instead of crashing., _SafeJSONResponse

### Community 6 - "Community 6"
Cohesion: 0.22
Nodes (9): _df_single_long_records(), get_mda(), Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only (+1 more)

### Community 7 - "Community 7"
Cohesion: 0.33
Nodes (8): database_url(), _ensure_journal(), get_conn(), migrate(), _pending(), Thin Postgres access for openst (D79 — retail savings bonds).  Reads ``DATABASE_, Open a plain psycopg2 connection. Requires ``DATABASE_URL`` to be set., Apply pending migrations from ``migrations/``, journaling each exactly once.

### Community 8 - "Community 8"
Cohesion: 0.4
Nodes (5): get_logo(), Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im, Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im, Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im, Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im

## Knowledge Gaps
- **89 isolated node(s):** `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Round and return a float, or None for NaN/None/non-numeric values.`, `Return an int, or None for NaN/None/non-numeric values.`, `Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin` (+84 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `parse_offer_emissions()` connect `FastAPI Endpoints` to `Community 5`?**
  _High betweenness centrality (0.358) - this node is a cross-community bridge._
- **Why does `_SafeJSONResponse` connect `Community 5` to `OpenBB Dividend Client`?**
  _High betweenness centrality (0.234) - this node is a cross-community bridge._
- **What connects `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Round and return a float, or None for NaN/None/non-numeric values.` to the rest of the system?**
  _89 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Redis Cache Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.11 - nodes in this community are weakly interconnected._
- **Should `OpenBB Dividend Client` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._
- **Should `FastAPI Endpoints` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._
- **Should `Dividend History Flow` be split into smaller, more focused modules?**
  _Cohesion score 0.09 - nodes in this community are weakly interconnected._