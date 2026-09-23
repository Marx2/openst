"""Shared dividendmax plugin test fixtures — fixture resolution + httpx.get mock."""

from pathlib import Path

import httpx
import pytest

from openbb_dividendmax import client

FIXTURES = Path(__file__).parents[3] / "tests" / "fixtures" / "dividendmax"


@pytest.fixture
def read_fixture():
    """Return a function reading a captured dividendmax fixture."""

    def _read(name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    return _read


@pytest.fixture
def httpx_mock(monkeypatch):
    """Replace ``client.httpx.get`` with a body queue and record the URLs.

    Queue entries are ``(body, status)`` tuples; ``body`` is JSON text for
    ``/suggest.json`` or raw HTML for a page. Subsequent calls fall back to a
    404.
    """

    def _mock(responses: list[tuple[str, int]]):
        calls = []

        def fake_get(url, **kwargs):
            calls.append(url)
            if responses:
                body, status = responses.pop(0)
            else:
                body, status = "", 404
            return httpx.Response(status, text=body, request=httpx.Request("GET", url))

        monkeypatch.setattr(client.httpx, "get", fake_get)
        return calls

    return _mock


@pytest.fixture
def no_delay(monkeypatch):
    """Zero the politeness delay for speed (the fixture queue has no network)."""
    monkeypatch.setenv(client.FETCH_DELAY_ENV, "0")
