# Graph Report - openst  (2026-10-07)

## Corpus Check
- 13 files · ~15,064 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 480 nodes · 813 edges · 26 communities
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fe97ced4`
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
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]

## God Nodes (most connected - your core abstractions)
1. `_cached_or_404()` - 29 edges
2. `_symbol_key()` - 29 edges
3. `_classify()` - 27 edges
4. `_provider_is_blocked()` - 22 edges
5. `_is_rate_limited()` - 21 edges
6. `_block_provider()` - 20 edges
7. `_plain()` - 20 edges
8. `_safe_float()` - 19 edges
9. `_is_invalid_ticker()` - 18 edges
10. `_df_records()` - 17 edges

## Surprising Connections (you probably didn't know these)
- `_SafeJSONResponse` --uses--> `RedisCache`  [INFERRED]
  main.py → cache.py
- `fund_search()` --calls--> `search()`  [INFERRED]
  main.py → importers/fund_catalogue.py
- `fund_search()` --calls--> `load_rows()`  [INFERRED]
  main.py → importers/fund_catalogue.py
- `dividend_yield()` --calls--> `get_dividend_yield()`  [EXTRACTED]
  main.py → openbb_client.py
- `price_history()` --calls--> `get_price_history()`  [EXTRACTED]
  main.py → openbb_client.py

## Communities (26 total, 0 thin omitted)

### Community 0 - "Redis Cache Layer"
Cohesion: 0.06
Nodes (85): Enum, _Action, _block_provider(), _check_pays_dividend(), _classify(), _crypto_search_row(), _df_records(), _forecast_status() (+77 more)

### Community 1 - "OpenBB Dividend Client"
Cohesion: 0.06
Nodes (63): _cached_or_404(), corp_bond_catalogue(), corp_bond_profile(), crypto_ohlcv(), crypto_profile(), crypto_quote(), crypto_search(), _default_dates() (+55 more)

### Community 2 - "FastAPI Endpoints"
Cohesion: 0.06
Nodes (33): get_company_news(), _news_source(), _plain(), Normalize an OpenBB `symbols` cell (comma string or list) to a symbol list., Resolve the news outlet name: prefer `publisher.name`, else the author string., Company news articles, provider-fallback across COMPANY_NEWS_PROVIDERS.      Rec, Normalize an OpenBB `symbols` cell (comma string or list) to a symbol list., Resolve the news outlet name: prefer `publisher.name`, else the author string. (+25 more)

### Community 3 - "Dividend History Flow"
Cohesion: 0.07
Nodes (30): Exception, _base_fund_code(), CatalogueUnavailable, load_rows(), Analizy.pl fund-category catalogue (plan §78).  Unlike every other catalogue her, ``ING01W`` -> ``ING01``; ``ING01`` -> ``ING01`` (already a fund).      Trailing, Case-insensitive match on code, alias or name. Empty query -> [].      Substring, The snapshot is missing or unparseable — a deployment fault, not a miss. (+22 more)

### Community 4 - "Package Init"
Cohesion: 0.09
Nodes (22): parse_offer_emissions(), Per-emission path URLs (``/oferta-obligacji/{slug}/{symbol}/``) listed on     th, Per-emission path URLs (``/oferta-obligacji/{slug}/{symbol}/``) listed on     th, Per-emission path URLs (``/oferta-obligacji/{slug}/{symbol}/``) listed on     th, Per-emission path URLs (``/oferta-obligacji/{slug}/{symbol}/``) listed on     th, _cell_text(), configure_logging(), fetch_catalogue() (+14 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (27): _bond_profile_from_db(), get_bond_profile(), get_corp_bond_profile(), get_institutional_ownership(), get_logo(), SEC Form 13F institutional holdings (filed quarterly by $100M+ AUM managers)., SEC Form 13F institutional holdings (filed quarterly by $100M+ AUM managers)., Resolve a logo URL for the ticker via the D34 chain.      1. FMP keyless CDN (im (+19 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (22): get_bond_ohlcv(), get_bond_quote(), get_crypto_profile(), _ohlcv_row(), Return an int, or None for NaN/None/non-numeric values., Return an int, or None for NaN/None/non-numeric values., Return an int, or None for NaN/None/non-numeric values., Return an int, or None for NaN/None/non-numeric values. (+14 more)

### Community 7 - "Community 7"
Cohesion: 0.1
Nodes (21): _analizy_currency(), get_fund_category_history(), _is_pence_currency(), _needs_gbx_normalization(), Pick the non-empty price series from an analizy.pl quotation payload.      Selec, Currency declared by the source, preferring the series' own value., NAV history for one Polish fund category, as [{"date", "close"}, ...].      `cod, Pick the non-empty price series from an analizy.pl quotation payload.      Selec (+13 more)

### Community 8 - "Community 8"
Cohesion: 0.12
Nodes (20): BondFetchError, Raised when obligacjeskarbowe.pl returns a non-200 for a fetch., Raised when obligacjeskarbowe.pl returns a non-200 for a fetch., Raised when obligacjeskarbowe.pl returns a non-200 for a fetch., Raised when obligacjeskarbowe.pl returns a non-200 for a fetch., build_url(), CpiFetchError, fetch_cpi() (+12 more)

### Community 9 - "Community 9"
Cohesion: 0.16
Nodes (17): configure_logging(), main(), parse_archive_codes(), Savings-bond series importer (D79 19.4) — obligacjeskarbowe.pl -> openst.bond_se, Emission ``(series_code, symbol)`` pairs from the ``/listy-emisyjne/`` selector., Emission ``(series_code, symbol, url_id)`` triples from the ``/listy-emisyjne/``, Emission ``(series_code, symbol, url_id)`` triples from the ``/listy-emisyjne/``, Fetch (and, with a DB, insert) emissions for a mode; returns a summary dict. (+9 more)

### Community 10 - "Community 10"
Cohesion: 0.15
Nodes (16): diff_report(), enabled(), object_census(), §73 — heap introspection for the openst memory leak.  Both replicas were OOMKill, Counts of the container types a leak would actually accumulate in.      Called o, The payload behind ``GET /__mem``.      Deliberately cheap enough to poll. ``rss, Largest growth between two :func:`snapshot` results.      This is the call that, True when heap tracing is running (i.e. ``MEM_DEBUG=1`` at boot). (+8 more)

### Community 11 - "Community 11"
Cohesion: 0.12
Nodes (16): _df_single_long_records(), get_mda(), Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only, Management Discussion & Analysis section from the latest SEC 10-K/10-Q (SEC-only, Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin, Return the single record from an OpenBB to_df() result.      Most OpenBB endpoin (+8 more)

### Community 12 - "Community 12"
Cohesion: 0.22
Nodes (9): _bond_search_from_db(), Search savings-bond emissions by symbol prefix or name substring (D79 19.7)., Search savings-bond emissions in Postgres (D79 21.3).      Matches every emissio, Crypto providers requiring a key are only tried when the key is set., Search savings-bond emissions in Postgres (D79 21.3).      Matches every emissio, Search savings-bond emissions by symbol prefix or name substring (D79 19.7)., Search savings-bond emissions in Postgres (D79 21.3).      Matches every emissio, Search savings-bond emissions by symbol prefix or name substring (D79 19.7). (+1 more)

### Community 13 - "Community 13"
Cohesion: 0.33
Nodes (8): database_url(), _ensure_journal(), get_conn(), migrate(), _pending(), Thin Postgres access for openst (D79 — retail savings bonds).  Reads ``DATABASE_, Open a plain psycopg2 connection. Requires ``DATABASE_URL`` to be set., Apply pending migrations from ``migrations/``, journaling each exactly once.

### Community 14 - "Community 14"
Cohesion: 0.22
Nodes (9): _classify_rate(), parse_emission(), Map the "Oprocentowanie" prose to a ``rate_rule`` value., Map the "Oprocentowanie" prose to a ``rate_rule`` value., Map the "Oprocentowanie" prose to a ``rate_rule`` value., Parse one emission offer page into a ``bond_series`` row dict.      Returns ``No, Parse one emission offer page into a ``bond_series`` row dict.      Returns ``No, Parse one emission offer page into a ``bond_series`` row dict.      Returns ``No (+1 more)

### Community 15 - "Community 15"
Cohesion: 0.22
Nodes (9): parse_detail_list(), Extract the ``product-details__list`` rows into a ``{label: value}`` map.      L, Extract the ``product-details__list`` rows into a ``{label: value}`` map.      L, Extract the ``product-details__list`` rows into a ``{label: value}`` map.      L, Extract the ``product-details__list`` rows into a ``{label: value}`` map.      L, First value whose normalised label starts with ``prefix`` (ASCII-safe)., First value whose normalised label starts with ``prefix`` (ASCII-safe)., First value whose normalised label starts with ``prefix`` (ASCII-safe). (+1 more)

### Community 16 - "Community 16"
Cohesion: 0.22
Nodes (9): add_months(), _page_text(), Whole-page text with scripts/styles stripped and whitespace normalised., Whole-page text with scripts/styles stripped and whitespace normalised., Whole-page text with scripts/styles stripped and whitespace normalised., Whole-page text with scripts/styles stripped and whitespace normalised., Calendar-add whole months, clamping the day to the target month's last day., Calendar-add whole months, clamping the day to the target month's last day. (+1 more)

### Community 17 - "Community 17"
Cohesion: 0.25
Nodes (8): _dec(), _extract_margin(), Parse a Polish number (comma decimal, possible "zł"/"%" suffix) as a Decimal., Parse a Polish number (comma decimal, possible "zł"/"%" suffix) as a Decimal., Parse a Polish number (comma decimal, possible "zł"/"%" suffix) as a Decimal., Pull the rate/margin percentage out of the "Oprocentowanie" prose.      * cpi-li, Map the "Oprocentowanie" prose to a ``rate_rule`` value., Pull the rate/margin percentage out of the "Oprocentowanie" prose.      * cpi-li

### Community 18 - "Community 18"
Cohesion: 0.4
Nodes (5): dumps(), json_safe(), JSON serialization that never emits invalid JSON and never corrupts strings.  pa, Return ``value`` with every non-finite float replaced by ``None``.      Recurses, Serialize to a JSON string that is always parseable.      ``default=str`` keeps

### Community 19 - "Community 19"
Cohesion: 0.33
Nodes (6): lifespan(), Apply schema migrations at boot when a database is configured.      Guarded by `, Apply schema migrations at boot when a database is configured.      Guarded by `, Apply schema migrations at boot when a database is configured.      Guarded by `, Apply schema migrations at boot when a database is configured.      Guarded by `, _run_migrations()

### Community 20 - "Community 20"
Cohesion: 0.5
Nodes (4): _ensure_otel(), OpenTelemetry bootstrap for openst (D56).  Sets up the Prometheus metric pipelin, One MeterProvider per process, shared by every app instance.      The global OTe, setup_otel()

### Community 21 - "Community 21"
Cohesion: 0.4
Nodes (5): fetch_page(), GET a page (following redirects); raise :class:`BondFetchError` on a non-200., GET a page (following redirects); raise :class:`BondFetchError` on a non-200., GET a page (following redirects); raise :class:`BondFetchError` on a non-200., GET a page (following redirects); raise :class:`BondFetchError` on a non-200.

### Community 22 - "Community 22"
Cohesion: 0.4
Nodes (5): Drop tags / entities-ish whitespace from an HTML fragment and normalise it., Drop tags / entities-ish whitespace from an HTML fragment and normalise it., Drop tags / entities-ish whitespace from an HTML fragment and normalise it., Drop tags / entities-ish whitespace from an HTML fragment and normalise it., _strip_tags()

### Community 23 - "Community 23"
Cohesion: 0.4
Nodes (5): _parse_pl_date(), Parse a Polish number (comma decimal, possible "zł"/"%" suffix) as a Decimal., Parse the first ``DD.MM.YYYY`` date in a fragment (Polish format)., Parse the first ``DD.MM.YYYY`` date in a fragment (Polish format)., Parse the first ``DD.MM.YYYY`` date in a fragment (Polish format).

### Community 24 - "Community 24"
Cohesion: 0.4
Nodes (5): _extract_fee(), Redemption fee ``b``: the *last* "opłata wynosi X zł" (current schedule),     fa, Redemption fee ``b``: the *last* "opłata wynosi X zł" (current schedule),     fa, Redemption fee ``b``: the *last* "opłata wynosi X zł" (current schedule),     fa, Redemption fee ``b``: the *last* "opłata wynosi X zł" (current schedule),     fa

## Knowledge Gaps
- **278 isolated node(s):** `Record a ticker in the bounded dividend cache.`, `Decide what a provider-walk loop does about an exception, and log it once.`, `Return True if ticker has any dividend history across all providers.`, `Record a resolved currency in the bounded currency cache.`, `True for pence-denominated currency labels.      OpenBB/yfinance labels LSE penc` (+273 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `parse_offer_emissions()` connect `Package Init` to `Community 9`?**
  _High betweenness centrality (0.301) - this node is a cross-community bridge._
- **Why does `_merged_dividend_calendar()` connect `Redis Cache Layer` to `Package Init`?**
  _High betweenness centrality (0.258) - this node is a cross-community bridge._
- **Why does `RedisCache` connect `Package Init` to `Dividend History Flow`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **What connects `Record a ticker in the bounded dividend cache.`, `Decide what a provider-walk loop does about an exception, and log it once.`, `Return True if ticker has any dividend history across all providers.` to the rest of the system?**
  _278 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Redis Cache Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.06 - nodes in this community are weakly interconnected._
- **Should `OpenBB Dividend Client` be split into smaller, more focused modules?**
  _Cohesion score 0.06 - nodes in this community are weakly interconnected._
- **Should `FastAPI Endpoints` be split into smaller, more focused modules?**
  _Cohesion score 0.06 - nodes in this community are weakly interconnected._