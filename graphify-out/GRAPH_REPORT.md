# Graph Report - openst  (2026-08-23)

## Corpus Check
- 4 files · ~1,866 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 46 nodes · 107 edges · 10 communities (9 shown, 1 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ccf95bcf`
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

## Communities (10 total, 1 thin omitted)

### Community 0 - "Redis Cache Layer"
Cohesion: 0.29
Nodes (7): _cached_or_404(), equity_fundamentals(), equity_metrics(), equity_profile(), equity_projections(), equity_quote(), equity_search()

### Community 1 - "OpenBB Dividend Client"
Cohesion: 0.33
Nodes (3): dividend_history(), dividend_yield(), price_history()

### Community 2 - "FastAPI Endpoints"
Cohesion: 0.5
Nodes (5): _check_pays_dividend(), get_dividend_yield(), _is_invalid_ticker(), Return True if ticker has any dividend history across all providers., Return True if ticker has any dividend history across all providers.

### Community 3 - "Dividend History Flow"
Cohesion: 0.7
Nodes (4): get_metrics(), get_profile(), get_quote(), _single_record()

### Community 4 - "Package Init"
Cohesion: 0.6
Nodes (5): _df_records(), get_calendar(), get_fundamentals(), _is_rate_limited(), search_equities()

### Community 5 - "Community 5"
Cohesion: 0.6
Nodes (5): _block_provider(), get_dividend_history(), get_ohlcv_history(), get_price_history(), _provider_is_blocked()

### Community 7 - "Community 7"
Cohesion: 0.5
Nodes (4): get_projections(), _plain(), Convert a pandas/numpy cell into a JSON-safe primitive., Convert a pandas/numpy cell into a JSON-safe primitive.

### Community 8 - "Community 8"
Cohesion: 0.67
Nodes (3): _default_dates(), equity_calendar(), price_ohlcv()

## Knowledge Gaps
- **4 isolated node(s):** `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Return True if ticker has any dividend history across all providers.`
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_check_pays_dividend()` connect `FastAPI Endpoints` to `Dividend History Flow`, `Package Init`, `Community 5`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Why does `_plain()` connect `Community 7` to `Dividend History Flow`, `Package Init`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **What connects `Return True if ticker has any dividend history across all providers.`, `Convert a pandas/numpy cell into a JSON-safe primitive.`, `Convert a pandas/numpy cell into a JSON-safe primitive.` to the rest of the system?**
  _4 weakly-connected nodes found - possible documentation gaps or missing edges._