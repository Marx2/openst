# Graph Report - ./src  (2026-05-26)

## Corpus Check
- Corpus is ~425 words - fits in a single context window. You may not need a graph.

## Summary
- 15 nodes · 16 edges · 5 communities (2 shown, 3 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Redis Cache Layer|Redis Cache Layer]]
- [[_COMMUNITY_OpenBB Dividend Client|OpenBB Dividend Client]]
- [[_COMMUNITY_FastAPI Endpoints|FastAPI Endpoints]]
- [[_COMMUNITY_Dividend History Flow|Dividend History Flow]]

## God Nodes (most connected - your core abstractions)
1. `RedisCache` - 4 edges
2. `_check_pays_dividend()` - 3 edges
3. `get_dividend_yield()` - 3 edges
4. `get_dividend_history()` - 2 edges
5. `dividend_yield()` - 2 edges
6. `dividend_history()` - 2 edges
7. `Return True if ticker has any dividend history across all providers.` - 1 edges

## Surprising Connections (you probably didn't know these)
- `dividend_yield()` --calls--> `get_dividend_yield()`  [EXTRACTED]
  main.py → openbb_client.py
- `dividend_history()` --calls--> `get_dividend_history()`  [EXTRACTED]
  main.py → openbb_client.py

## Communities (5 total, 3 thin omitted)

### Community 1 - "OpenBB Dividend Client"
Cohesion: 0.67
Nodes (3): _check_pays_dividend(), get_dividend_yield(), Return True if ticker has any dividend history across all providers.

## Knowledge Gaps
- **1 isolated node(s):** `Return True if ticker has any dividend history across all providers.`
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `dividend_yield()` connect `FastAPI Endpoints` to `OpenBB Dividend Client`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **What connects `Return True if ticker has any dividend history across all providers.` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._