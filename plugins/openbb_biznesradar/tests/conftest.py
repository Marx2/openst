"""Shared plugin test fixtures (D77 16.4) — fixture resolution + httpx.get mock."""

from pathlib import Path

import httpx
import pytest

from openbb_biznesradar import scraper

FIXTURES = Path(__file__).parents[3] / "tests" / "fixtures" / "biznesradar"

TERMINAL_PAGE = "<html><body><table class='qTableFull'></table></body></html>"


@pytest.fixture
def read_fixture():
    """Return a function reading a captured biznesradar fixture page."""

    def _read(name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    return _read


@pytest.fixture
def build_page():
    """Return a function building an inline qTableFull page (``nxt`` = next-page link)."""

    def _build(rows: list[tuple], *, nxt: bool) -> str:
        body = "".join(
            "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows
        )
        footer = (
            '<div class="buttons pages"><a class="pages_right" title="następna"></a></div>'
            if nxt
            else '<div class="buttons pages"></div>'
        )
        return f"<html><body><table class='qTableFull'>{body}</table>{footer}</body></html>"

    return _build


@pytest.fixture
def httpx_mock(monkeypatch):
    """Replace ``scraper.httpx.get`` with a page queue and record the URLs.

    Usage::

        calls = httpx_mock([(read_fixture("NNEP25.TFI.html"), 200)])
        # subsequent calls fall back to a terminal (no-pagination) page
    """

    def _mock(pages: list[tuple[str, int]]):
        calls = []

        def fake_get(url, **kwargs):
            calls.append(url)
            if pages:
                html, status = pages.pop(0)
            else:
                html, status = TERMINAL_PAGE, 200
            return httpx.Response(status, text=html, request=httpx.Request("GET", url))

        monkeypatch.setattr(scraper.httpx, "get", fake_get)
        return calls

    return _mock