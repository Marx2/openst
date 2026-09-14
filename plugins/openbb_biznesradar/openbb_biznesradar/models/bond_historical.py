"""Catalyst corporate bond table parser — 7-column OHLCV (D77 16.4).

Column indices (confirmed from ``tests/fixtures/biznesradar/BST0327.html``):
``{date: 0, open: 1, high: 2, low: 3, close: 4, volume: 5}``.  The 7th column
(``Obrót``, turnover) is not exposed in the output model.
"""

from __future__ import annotations

BOND_COLUMNS = {"date": 0, "open": 1, "high": 2, "low": 3, "close": 4, "volume": 5}


def parse_bond_row(row: dict) -> dict:
    """Map a scraped bond row (``{date, open, high, low, close, volume}``) to the OHLCV model shape."""
    return {
        "date": row["date"],
        "open": row["open"],
        "high": row["high"],
        "low": row["low"],
        "close": row["close"],
        "volume": row["volume"],
    }