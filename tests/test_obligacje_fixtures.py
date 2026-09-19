"""Fixture sanity checks for obligacje.pl (D80, step 25.1).

These tests only pin the captured HTML so that the parser implemented in
step 25.2 has a stable contract. Selectors: see tests/fixtures/obligacje/README.md.
"""

import re
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
PROFILE_FIXTURE = FIXTURES / "obligacje_bond_profile_BST0327.html"
CATALOGUE_FIXTURE = FIXTURES / "obligacje_bond_catalogue_page1.html"


def _text(fragment: str) -> str:
    return re.sub(r"<[^>]+>", " ", fragment)


def _profile_field(label: str) -> str:
    html = PROFILE_FIXTURE.read_text(encoding="utf-8")
    m = re.search(
        rf"<th>{label}:</th>\s*<td[^>]*>(.*?)</td>", html, re.S
    )
    assert m, f"profile field {label!r} not found"
    return re.sub(r"\s+", " ", _text(m.group(1))).strip()


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Emitent", "Best S.A."),
        ("Seria", "W3"),
        ("ISIN", "PLBEST000333"),
        ("Rynek", "GPW RR"),
        ("Status", "Notowane"),
        ("Wartość nominalna", "100.00 PLN"),
        ("Typ oprocentowania", "zmienne WIBOR 3M + 4%"),
        ("Oprocentowanie bieżące", "7.83%"),
    ],
)
def test_profile_fields(label, expected):
    assert _profile_field(label) == expected


def test_profile_maturity():
    html = PROFILE_FIXTURE.read_text(encoding="utf-8")
    m = re.search(
        r"<h4>Dzień wykupu</h4>.*?<li>(\d{4}-\d{2}-\d{2})</li>", html, re.S
    )
    assert m
    assert m.group(1) == "2027-03-07"


def test_catalogue_rows():
    html = CATALOGUE_FIXTURE.read_text(encoding="utf-8")
    table = re.search(r'<table id="tabela".*?</table>', html, re.S)
    assert table, "catalogue table #tabela not found"
    rows = re.findall(r"<tr>\s*(<td>.*?</tr>)", table.group(0), re.S)
    assert len(rows) == 937
    symbols = re.findall(r'href="/pl/obligacja/([^"]+)"', table.group(0))
    assert len(symbols) == len(set(symbols)), "duplicate bond symbols"
    # first fixture row: 7R S.A. / SIR0228, maturity 2028-02-04
    first = rows[0]
    cells = [_text(c).strip() for c in re.findall(r"<td>(.*?)</td>", first, re.S)]
    assert cells[0] == "7R S.A."
    assert cells[1] == "SIR0228"
    assert cells[2] == "2028-02-04"
    assert cells[3] == "zmienne WIBOR 6M"
    assert cells[4] == "4.8"
    assert cells[5] == "8.64%"


def test_catalogue_has_no_server_pagination():
    html = CATALOGUE_FIXTURE.read_text(encoding="utf-8")
    assert "table_info" not in html
    assert not re.search(r'wyszukiwarka-obligacji-notowanych[^"]*(page=|\?)', html)
