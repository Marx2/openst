# Graph Report - openst  (2026-08-23)

## Corpus Check
- 4 files · ~1,722 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 45 nodes · 105 edges · 9 communities (8 shown, 1 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8b904645`
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

## God Nodes (most connected - your core abstractions)
1. `_is_rate_limited()` - 10 edges
2. `_block_provider()` - 10 edges
3. `_provider_is_blocked()` - 10 edges
4. `_single_record()` - 10 edges
5. `_is_invalid_ticker()` - 9 edges
6. `_cached_or_404()` - 9 edges
7. `_check_pays_dividend()` - 8 edges
8. `get_dividend_yield()` - 7 edges
9. `get_price_history()` - 6 edges
10. `get_dividend_history()` - 6 edges

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

## Communities (9 total, 1 thin omitted)

### Community 0 - "Redis Cache Layer"
Cohesion: 0.57
Nodes (7): get_dividend_history(), get_fundamentals(), get_ohlcv_history(), get_price_history(), _is_invalid_ticker(), _is_rate_limited(), _provider_is_blocked()

### Community 1 - "OpenBB Dividend Client"
Cohesion: 0.29
Nodes (7): _cached_or_404(), equity_fundamentals(), equity_metrics(), equity_profile(), equity_projections(), equity_quote(), equity_search()

### Community 2 - "FastAPI Endpoints"
Cohesion: 0.53
Nodes (5): _df_records(), get_calendar(), _plain(), Convert a pandas/numpy cell into a JSON-safe primitive., search_equities()

### Community 3 - "Dividend History Flow"
Cohesion: 0.33
Nodes (3): dividend_history(), dividend_yield(), price_history()

### Community 4 - "Package Init"
Cohesion: 0.4
Nodes (5): get_metrics(), get_profile(), get_projections(), get_quote(), _single_record()

### Community 5 - "Community 5"
Cohesion: 0.5
Nodes (5): _block_provider(), _check_pays_dividend(), get_dividend_yield(), Return True if ticker has any dividend history across all providers., Return True if ticker has any dividend history across all providers.

### Community 7 - "Community 7"
Cohesion: 0.67
Nodes (3): _default_dates(), equity_calendar(), price_ohlcv()

## Knowledge Gaps
- **3 isolated node(s):** `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Return True if ticker has any dividend history across all providers.`
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_check_pays_dividend()` connect `Community 5` to `Redis Cache Layer`, `FastAPI Endpoints`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **What connects `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Return True if ticker has any dividend history across all providers.` to the rest of the system?**
  _3 weakly-connected nodes found - possible documentation gaps or missing edges._