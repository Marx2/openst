"""§73 — heap introspection for the openst memory leak.

Both replicas were OOMKilled at a 700Mi limit with monotonic RSS growth and 8
restarts in 7 days. Raising the ceiling to 2Gi (homelab `96df0fc`) is mitigation
and was labelled as such: it buys time, it does not explain anything.

Nothing in this repository retains memory. The only unbounded container is the
404 negative cache, and that lives in Redis with a 6h TTL, not in the process.
The 29 `obb.*` calls go through OpenBB's module-level singleton, whose internal
provider/DataFrame caches are not ours to read from here — and the earlier
"logo/search correlate with growth" observation is correlation, not evidence,
since the SPA's research page fires both together.

So this module does the one thing that is possible without a live restart cycle:
it draws the line between the two kinds of growth, which is the first question
worth answering.

- **Python-heap growth** shows up in `tracemalloc` snapshots. The cause is a
  container we can find by reading a diff, and a fix is ours to make.
- **Native growth** — OpenBB's C extensions, numpy/pandas buffers, a native
  provider client — is largely invisible to `tracemalloc`, which counts Python
  allocations only. `tracemalloc` small, RSS large means the leak is not ours.

Without that split, "add tracemalloc and watch" sounds like a plan and turns out
to be a week of staring at a graph. With it, the first snapshot pair answers the
question.

`tracemalloc` is started lazily and only when `MEM_DEBUG=1`. Left on permanently
it adds real per-allocation overhead to a latency-sensitive service, which is not
a trade worth making to diagnose a leak that may not be a Python leak at all.
"""

from __future__ import annotations

import gc
import os
import time
import tracemalloc
from typing import Any

_ENABLED = os.environ.get("MEM_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}

#: How many top allocation sites to report. Enough to name a module, few enough
#: that the endpoint stays cheap to scrape.
TOP_N = 12


def enabled() -> bool:
    """True when heap tracing is running (i.e. ``MEM_DEBUG=1`` at boot)."""
    return tracemalloc.is_tracing()


def start() -> None:
    """Start tracing. No-op when already running, and a no-op without ``MEM_DEBUG``.

    Called from the lifespan hook so the numbers cover process start rather than
    beginning mid-incident.
    """
    if not _ENABLED or tracemalloc.is_tracing():
        return
    # 25 frames is well past the useful depth for attributing a leak to a module
    # and keeps snapshot cost sane.
    tracemalloc.start(25)


def snapshot() -> tracemalloc.Snapshot | None:
    """Take a heap snapshot, or ``None`` when tracing is off."""
    if not tracemalloc.is_tracing():
        return None
    return tracemalloc.take_snapshot()


def rss_bytes() -> int:
    """Resident set size in bytes, 0 only if the platform offers no way to read it.

    Linux first, from ``/proc/self/statm``: one read of one line, no parsing
    (the same number is in ``VmRSS`` under ``/proc/self/status``).

    The fallback matters more than it looks. Returning 0 for an unreadable RSS is
    indistinguishable from a process using no memory, which is the exact
    misreading this module exists to prevent — and the first test written here
    failed on macOS for precisely that reason. ``getrusage`` covers the BSD/macOS
    case, at the cost of one unit trap: ``ru_maxrss`` is BYTES on macOS and
    KILOBYTES on Linux, so it is only consulted off-Linux and scaled explicitly.
    """
    try:
        with open("/proc/self/statm", "r", encoding="ascii") as fh:
            pages = int(fh.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, IndexError, ValueError):
        pass

    try:
        import resource

        # Only reached when /proc is absent, i.e. not Linux, where the value is bytes.
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except Exception:  # noqa: BLE001 - platform without /proc or getrusage
        return 0


def object_census(limit: int = TOP_N) -> dict[str, int]:
    """Counts of the container types a leak would actually accumulate in.

    Called out explicitly because these are the shapes that grow silently: a dict
    used as a memo, a list that is appended to and never trimmed, a ``defaultdict``
    keyed per ticker, a ``set`` of cache keys. A `gc`-based census cannot see
    objects the collector considers untracked, so the numbers are indicative of
    order of magnitude, not exact.
    """
    gc.collect()
    counts: dict[str, int] = {}
    for obj in gc.get_objects():
        try:
            name = type(obj).__name__
        except Exception:  # noqa: BLE001 - a proxy type with a broken __name__
            continue
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1])[:limit])


def report() -> dict[str, Any]:
    """The payload behind ``GET /__mem``.

    Deliberately cheap enough to poll. ``rss`` and ``traced`` are the two numbers
    that matter for triage: if ``traced`` is a small fraction of ``rss`` the growth
    is native and outside this codebase.
    """
    snap = snapshot()
    traced = sum(stat.size for stat in snap.statistics("filename")) if snap else 0
    rss = rss_bytes()
    out: dict[str, Any] = {
        "service": "openst",
        "rss_bytes": rss,
        "traced_bytes": traced,
        # The ratio is the whole point: small traced + large rss => not ours.
        "traced_fraction": round(traced / rss, 4) if rss else None,
        "tracing": enabled(),
        "uptime_s": int(_uptime()),
    }
    if snap is not None:
        out["top_allocations"] = [
            {
                "location": stat.traceback[0].filename,
                "size_bytes": stat.size,
                "count": stat.count,
            }
            for stat in snap.statistics("filename")[:TOP_N]
        ]
    return out


def diff_report(before: Any, after: Any, top_n: int = TOP_N) -> list[dict[str, Any]]:
    """Largest growth between two :func:`snapshot` results.

    This is the call that actually names a cause, and it needs two samples taken
    minutes apart with traffic in between — a single sample only says where memory
    is, which for a long-lived process is mostly wherever the cache is.

    Returns ``[]`` rather than raising when either snapshot is missing, so a
    scraper can call it unconditionally.
    """
    if before is None or after is None:
        return []
    return [
        {
            "location": stat.traceback[0].filename,
            "size_diff_bytes": stat.size_diff,
            "count_diff": stat.count_diff,
        }
        for stat in after.compare_to(before, "filename")[:top_n]
        if stat.size_diff > 0
    ]


_STARTED_AT = time.monotonic()


def _uptime() -> float:
    return time.monotonic() - _STARTED_AT
