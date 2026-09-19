# Graph Report - openst  (2026-09-16)

## Corpus Check
- 9 files · ~7,493 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 270 nodes · 465 edges · 19 communities
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.65)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8d3834e8`
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
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]

## God Nodes (most connected - your core abstractions)
1. `_cached_or_404()` - 23 edges
2. `_is_rate_limited()` - 19 edges
3. `_block_provider()` - 19 edges
4. `_provider_is_blocked()` - 19 edges
5. `_plain()` - 18 edges
6. `_is_invalid_ticker()` - 16 edges
7. `parse_emission()` - 14 edges
8. `_safe_float()` - 13 edges
9. `_df_records()` - 13 edges
10. `get_company_news()` - 13 edges

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

## Communities (19 total, 0 thin omitted)

### Community 0 - "Redis Cache Layer"
Cohesion: 0.1
Nodes (48): _block_provider(), _check_pays_dividend(), _df_records(), get_calendar(), get_crypto_ohlcv(), get_crypto_quote(), get_crypto_search(), get_dividend_history() (+40 more)

### Community 1 - "OpenBB Dividend Client"
Cohesion: 0.07
Nodes (38): _cached_or_404(), crypto_ohlcv(), crypto_profile(), crypto_quote(), crypto_search(), _default_dates(), dividend_history(), dividend_yield() (+30 more)

### Community 2 - "FastAPI Endpoints"
Cohesion: 0.07
Nodes (30): _bond_search_from_db(), get_company_news(), _news_source(), _plain(), Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive. (+22 more)

### Community 3 - "Dividend History Flow"
Cohesion: 0.12
Nodes (17): _bond_profile_from_db(), get_bond_profile(), get_institutional_ownership(), get_logo(), SEC Form 13F institutional holdings (filed quarterly by $100M+ AUM managers)., Issue parameters for a known savings-bond emission (D79 19.7).      Calls ``obb., Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im, Read a bond emission's 10-column row from Postgres (D79 21.3).      Returns ``No (+9 more)

### Community 4 - "Package Init"
Cohesion: 0.17
Nodes (15): build_url(), CpiFetchError, fetch_cpi(), main(), parse_cpi_rows(), CPI importer (D79 19.3) — obligacje.pl 12m inflation -> openst.cpi_12m.  Data so, Fetch (+ possibly insert) CPI data for a mode; returns a summary dict., Raised when obligacje.pl returns a non-200 or a page with no CPI rows. (+7 more)

### Community 5 - "Community 5"
Cohesion: 0.2
Nodes (13): main(), parse_archive_codes(), Savings-bond series importer (D79 19.4) — obligacjeskarbowe.pl -> openst.bond_se, Emission ``(series_code, symbol)`` pairs from the ``/listy-emisyjne/`` selector., Emission ``(series_code, symbol, url_id)`` triples from the ``/listy-emisyjne/``, Fetch (and, with a DB, insert) emissions for a mode; returns a summary dict., Fetch (and, with a DB, insert) emissions for a mode; returns a summary dict., Fetch (and, with a DB, insert) emissions for a mode; returns a summary dict. (+5 more)

### Community 6 - "Community 6"
Cohesion: 0.15
Nodes (8): _JSONResponse, RedisCache, JSONResponse that serializes NaN/Inf floats as null instead of crashing., JSONResponse that serializes NaN/Inf floats as null instead of crashing., JSONResponse that serializes NaN/Inf floats as null instead of crashing., JSONResponse that serializes NaN/Inf floats as null instead of crashing., JSONResponse that serializes NaN/Inf floats as null instead of crashing., _SafeJSONResponse

### Community 7 - "Community 7"
Cohesion: 0.17
Nodes (12): _df_single_long_records(), get_mda(), Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only (+4 more)

### Community 8 - "Community 8"
Cohesion: 0.2
Nodes (11): add_months(), _page_text(), parse_emission(), Whole-page text with scripts/styles stripped and whitespace normalised., Whole-page text with scripts/styles stripped and whitespace normalised., Whole-page text with scripts/styles stripped and whitespace normalised., Calendar-add whole months, clamping the day to the target month's last day., Calendar-add whole months, clamping the day to the target month's last day. (+3 more)

### Community 9 - "Community 9"
Cohesion: 0.18
Nodes (11): parse_detail_list(), Drop tags / entities-ish whitespace from an HTML fragment and normalise it., Drop tags / entities-ish whitespace from an HTML fragment and normalise it., Drop tags / entities-ish whitespace from an HTML fragment and normalise it., Extract the ``product-details__list`` rows into a ``{label: value}`` map.      L, Extract the ``product-details__list`` rows into a ``{label: value}`` map.      L, Extract the ``product-details__list`` rows into a ``{label: value}`` map.      L, First value whose normalised label starts with ``prefix`` (ASCII-safe). (+3 more)

### Community 10 - "Community 10"
Cohesion: 0.2
Nodes (10): _dec(), _extract_fee(), _extract_margin(), Parse a Polish number (comma decimal, possible "zł"/"%" suffix) as a Decimal., Parse a Polish number (comma decimal, possible "zł"/"%" suffix) as a Decimal., Pull the rate/margin percentage out of the "Oprocentowanie" prose.      * cpi-li, Pull the rate/margin percentage out of the "Oprocentowanie" prose.      * cpi-li, Redemption fee ``b``: the *last* "opłata wynosi X zł" (current schedule),     fa (+2 more)

### Community 11 - "Community 11"
Cohesion: 0.33
Nodes (8): database_url(), _ensure_journal(), get_conn(), migrate(), _pending(), Thin Postgres access for openst (D79 — retail savings bonds).  Reads ``DATABASE_, Open a plain psycopg2 connection. Requires ``DATABASE_URL`` to be set., Apply pending migrations from ``migrations/``, journaling each exactly once.

### Community 12 - "Community 12"
Cohesion: 0.25
Nodes (8): get_bond_ohlcv(), Return an int, or None for NaN/None/non-numeric values., Return an int, or None for NaN/None/non-numeric values., Return an int, or None for NaN/None/non-numeric values., Return an int, or None for NaN/None/non-numeric values., Priced redemption OHLCV series for a savings-bond emission (D79 19.7).      Call, Priced redemption OHLCV series for a savings-bond emission (D79 19.7).      Call, _safe_int()

### Community 13 - "Community 13"
Cohesion: 0.25
Nodes (8): BondFetchError, fetch_page(), Raised when obligacjeskarbowe.pl returns a non-200 for a fetch., Raised when obligacjeskarbowe.pl returns a non-200 for a fetch., Raised when obligacjeskarbowe.pl returns a non-200 for a fetch., GET a page (following redirects); raise :class:`BondFetchError` on a non-200., GET a page (following redirects); raise :class:`BondFetchError` on a non-200., GET a page (following redirects); raise :class:`BondFetchError` on a non-200.

### Community 14 - "Community 14"
Cohesion: 0.5
Nodes (4): _classify_rate(), Map the "Oprocentowanie" prose to a ``rate_rule`` value., Map the "Oprocentowanie" prose to a ``rate_rule`` value., Map the "Oprocentowanie" prose to a ``rate_rule`` value.

### Community 15 - "Community 15"
Cohesion: 0.5
Nodes (4): parse_offer_emissions(), Per-emission path URLs (``/oferta-obligacji/{slug}/{symbol}/``) listed on     th, Per-emission path URLs (``/oferta-obligacji/{slug}/{symbol}/``) listed on     th, Per-emission path URLs (``/oferta-obligacji/{slug}/{symbol}/``) listed on     th

### Community 16 - "Community 16"
Cohesion: 0.5
Nodes (4): _parse_pl_date(), Parse a Polish number (comma decimal, possible "zł"/"%" suffix) as a Decimal., Parse the first ``DD.MM.YYYY`` date in a fragment (Polish format)., Parse the first ``DD.MM.YYYY`` date in a fragment (Polish format).

### Community 17 - "Community 17"
Cohesion: 0.67
Nodes (3): get_crypto_profile(), Crypto profile derived from the quote response (no dedicated profile endpoint)., Crypto profile derived from the quote response (no dedicated profile endpoint).

## Knowledge Gaps
- **140 isolated node(s):** `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Round and return a float, or None for NaN/None/non-numeric values.`, `Return an int, or None for NaN/None/non-numeric values.`, `Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin` (+135 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `parse_offer_emissions()` connect `Community 15` to `Community 5`, `Community 6`?**
  _High betweenness centrality (0.407) - this node is a cross-community bridge._
- **Why does `_SafeJSONResponse` connect `Community 6` to `OpenBB Dividend Client`?**
  _High betweenness centrality (0.246) - this node is a cross-community bridge._
- **What connects `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Round and return a float, or None for NaN/None/non-numeric values.` to the rest of the system?**
  _140 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Redis Cache Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._
- **Should `OpenBB Dividend Client` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._
- **Should `FastAPI Endpoints` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._
- **Should `Dividend History Flow` be split into smaller, more focused modules?**
  _Cohesion score 0.12 - nodes in this community are weakly interconnected._