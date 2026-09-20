"""plan §37.4 — the upstream concurrency gate bounds in-flight provider walks.

Drives ``_cached_or_404``'s fetch path (fake cache = always a miss) with a
fetch that parks every worker until an ``Event`` is set. Because all parked
workers hold the gate slots, the peak in-flight count is a clean measure of
how many concurrent fetches the gate admits.
"""
import threading
from unittest.mock import patch

import src.main as m


class _FakeCache:
    def get(self, key):
        return None  # always a miss → always through the fetch path

    def set(self, key, value, ttl=86400):
        pass


def test_gate_caps_in_flight_fetches():
    bound = 3
    workers = 9
    fake_cache = _FakeCache()

    in_flight = 0
    max_in_flight = 0
    lock = threading.Lock()
    release = threading.Event()

    def parking_fetch():
        nonlocal in_flight, max_in_flight
        with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        release.wait(timeout=10)
        with lock:
            in_flight -= 1
        return {"ok": True}

    def controller():
        # Release only once the gate is fully occupied. If the gate admitted
        # more than its bound, in_flight would have already peaked past it.
        while True:
            with lock:
                if in_flight >= bound:
                    break
            threading.Event().wait(0.01)
        with lock:
            observed = max_in_flight
        release.set()
        assert observed <= bound, f"gate allowed {observed} in-flight fetches (bound {bound})"

    ctrl = threading.Thread(target=controller)
    with (
        patch("src.main._cache", fake_cache),
        patch("src.main._upstream_gate", threading.Semaphore(bound)),
    ):
        ctrl.start()
        threads = [
            threading.Thread(target=lambda i=i: m._cached_or_404(f"k{i}", parking_fetch, "nf"))
            for i in range(workers)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)
        ctrl.join(timeout=15)
        assert not any(t.is_alive() for t in threads + [ctrl]), "deadlock"

    # the gate admitted exactly its bound of concurrent fetches (no more),
    # while still allowing real parallelism
    assert max_in_flight == bound
