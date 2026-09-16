# Graph Report - openst  (2026-09-16)

## Corpus Check
- 9 files · ~7,107 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 236 nodes · 422 edges · 11 communities
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.65)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `434b088d`
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

## God Nodes (most connected - your core abstractions)
1. `_cached_or_404()` - 23 edges
2. `_is_rate_limited()` - 19 edges
3. `_block_provider()` - 19 edges
4. `_provider_is_blocked()` - 19 edges
5. `_is_invalid_ticker()` - 16 edges
6. `_plain()` - 15 edges
7. `_df_records()` - 13 edges
8. `parse_emission()` - 13 edges
9. `_safe_float()` - 12 edges
10. `get_company_news()` - 12 edges

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

## Communities (11 total, 0 thin omitted)

### Community 0 - "Redis Cache Layer"
Cohesion: 0.06
Nodes (49): add_months(), BondFetchError, _classify_rate(), _dec(), _extract_fee(), _extract_margin(), fetch_page(), main() (+41 more)

### Community 1 - "OpenBB Dividend Client"
Cohesion: 0.11
Nodes (48): _block_provider(), _check_pays_dividend(), _df_records(), get_bond_profile(), get_calendar(), get_crypto_ohlcv(), get_crypto_profile(), get_crypto_quote() (+40 more)

### Community 2 - "FastAPI Endpoints"
Cohesion: 0.07
Nodes (38): _cached_or_404(), crypto_ohlcv(), crypto_profile(), crypto_quote(), crypto_search(), _default_dates(), dividend_history(), dividend_yield() (+30 more)

### Community 3 - "Dividend History Flow"
Cohesion: 0.1
Nodes (22): get_company_news(), get_projections(), _news_source(), _plain(), Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive. (+14 more)

### Community 4 - "Package Init"
Cohesion: 0.12
Nodes (11): parse_offer_emissions(), Per-emission path URLs (``/oferta-obligacji/{slug}/{symbol}/``) listed on     th, Per-emission path URLs (``/oferta-obligacji/{slug}/{symbol}/``) listed on     th, _JSONResponse, RedisCache, JSONResponse that serializes NaN/Inf floats as null instead of crashing., JSONResponse that serializes NaN/Inf floats as null instead of crashing., JSONResponse that serializes NaN/Inf floats as null instead of crashing. (+3 more)

### Community 5 - "Community 5"
Cohesion: 0.17
Nodes (15): build_url(), CpiFetchError, fetch_cpi(), main(), parse_cpi_rows(), CPI importer (D79 19.3) — obligacje.pl 12m inflation -> openst.cpi_12m.  Data so, Fetch (+ possibly insert) CPI data for a mode; returns a summary dict., Raised when obligacje.pl returns a non-200 or a page with no CPI rows. (+7 more)

### Community 6 - "Community 6"
Cohesion: 0.18
Nodes (11): get_institutional_ownership(), get_logo(), SEC Form 13F institutional holdings (filed quarterly by $100M+ AUM managers)., Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im, SEC Form 13F institutional holdings (filed quarterly by $100M+ AUM managers)., Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im, SEC Form 13F institutional holdings (filed quarterly by $100M+ AUM managers)., SEC Form 13F institutional holdings (filed quarterly by $100M+ AUM managers). (+3 more)

### Community 7 - "Community 7"
Cohesion: 0.2
Nodes (10): _df_single_long_records(), get_mda(), Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only (+2 more)

### Community 8 - "Community 8"
Cohesion: 0.33
Nodes (8): database_url(), _ensure_journal(), get_conn(), migrate(), _pending(), Thin Postgres access for openst (D79 — retail savings bonds).  Reads ``DATABASE_, Open a plain psycopg2 connection. Requires ``DATABASE_URL`` to be set., Apply pending migrations from ``migrations/``, journaling each exactly once.

### Community 9 - "Community 9"
Cohesion: 0.33
Nodes (6): get_bond_ohlcv(), Return an int, or None for NaN/None/non-numeric values., Return an int, or None for NaN/None/non-numeric values., Return an int, or None for NaN/None/non-numeric values., Priced redemption OHLCV series for a savings-bond emission (D79 19.7).      Call, _safe_int()

## Knowledge Gaps
- **113 isolated node(s):** `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Round and return a float, or None for NaN/None/non-numeric values.`, `Return an int, or None for NaN/None/non-numeric values.`, `Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin` (+108 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `parse_offer_emissions()` connect `Package Init` to `Redis Cache Layer`?**
  _High betweenness centrality (0.393) - this node is a cross-community bridge._
- **Why does `_SafeJSONResponse` connect `Package Init` to `FastAPI Endpoints`?**
  _High betweenness centrality (0.247) - this node is a cross-community bridge._
- **What connects `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Round and return a float, or None for NaN/None/non-numeric values.` to the rest of the system?**
  _113 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Redis Cache Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.06 - nodes in this community are weakly interconnected._
- **Should `OpenBB Dividend Client` be split into smaller, more focused modules?**
  _Cohesion score 0.11 - nodes in this community are weakly interconnected._
- **Should `FastAPI Endpoints` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._
- **Should `Dividend History Flow` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._