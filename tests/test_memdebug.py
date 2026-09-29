"""§73 — the memory endpoint must answer the question it exists to answer.

The leak itself cannot be tested here (it needs a live restart cycle and real
traffic), but the split it depends on is fully testable: does `traced_bytes` track
`rss_bytes` when tracing is on, and is it honestly reported as "not tracing" when
it is off? A diagnostic that lies when disabled is worse than none, because it
reads as an empty heap rather than a missing measurement.
"""

from __future__ import annotations

import tracemalloc

import pytest

from src import memdebug


def test_report_is_cheap_and_typed_without_tracing():
    r = memdebug.report()
    assert r["service"] == "openst"
    # Portable, not Linux-only: /proc on Linux, getrusage elsewhere. A 0 here
    # would be indistinguishable from an empty heap, which is the misreading the
    # module exists to prevent — and the first version of this test failed on
    # macOS because rss_bytes() only knew about /proc.
    assert r["rss_bytes"] > 0
    assert "traced_fraction" in r
    assert isinstance(r["uptime_s"], int)
    assert r["uptime_s"] >= 0


def test_reports_not_tracing_honestly_rather_than_as_an_empty_heap():
    # tracemalloc off: traced_bytes must be 0 AND tracing must say so. Reporting
    # 0 traced with no flag is indistinguishable from "the heap is empty", which
    # is precisely the misreading that would send someone hunting a Python leak
    # that does not exist.
    if not tracemalloc.is_tracing():
        r = memdebug.report()
        assert r["traced_bytes"] == 0
        assert r["tracing"] is False
        assert "top_allocations" not in r


def test_traced_bytes_follows_real_allocation_when_tracing():
    tracemalloc.start(5)
    try:
        before = memdebug.report()["traced_bytes"]
        ballast = [bytearray(2_000_000) for _ in range(4)]  # ~8MB, unambiguously ours
        after = memdebug.report()["traced_bytes"]
        assert after > before, "8MB of live objects must show up in traced_bytes"
        del ballast
    finally:
        tracemalloc.stop()


def test_snapshot_diff_names_a_growing_allocation_site():
    tracemalloc.start(5)
    try:
        before = memdebug.snapshot()
        ballast = [bytearray(1_000_000) for _ in range(3)]
        after = memdebug.snapshot()
        grew = memdebug.diff_report(before, after)
        assert grew, "a 3MB allocation must appear in the diff"
        assert all(g["size_diff_bytes"] > 0 for g in grew)
        assert grew[0]["size_diff_bytes"] >= 1_000_000
        del ballast
    finally:
        tracemalloc.stop()


def test_diff_report_degrades_instead_of_raising_without_snapshots():
    # A scraper calls this unconditionally; it must not need a guard of its own.
    assert memdebug.diff_report(None, None) == []


def test_object_census_finds_the_container_we_actually_grew():
    counts = memdebug.object_census(limit=40)
    assert counts, "a census of a live process is never empty"
    # Ordered by size, descending.
    values = list(counts.values())
    assert values == sorted(values, reverse=True)
