"""Catalyst corporate bond table parser — 7-column OHLCV (D77 16.4).

Column indices (confirmed from ``tests/fixtures/biznesradar/BST0327.html``):
``{date: 0, open: 1, high: 2, low: 3, close: 4, volume: 5}``.  The 7th column
(``Obrót``, turnover) is not exposed in the output model.
"""

BOND_COLUMNS = {"date": 0, "open": 1, "high": 2, "low": 3, "close": 4, "volume": 5}


def parse_bond_row(row: tuple[str, str, str, str, str, str, str]) -> dict:
    """Map a 7-column (Data|Otwarcie|Max|Min|Zamknięcie|Wolumen|Obrót) row to an EquityHistorical-shaped dict."""
    raise NotImplementedError  # implemented in 16.4