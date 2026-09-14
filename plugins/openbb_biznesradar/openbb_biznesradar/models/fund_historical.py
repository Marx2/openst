"""TFI/FIZ open-end fund table parser — 2-column Data|Kurs (D77 16.4).

Column indices (confirmed from ``tests/fixtures/biznesradar/NNEP25.TFI.html``):
``{date: 0, close: 1}``.
"""

from __future__ import annotations

FUND_COLUMNS = {"date": 0, "close": 1}


def parse_fund_row(row: dict) -> dict:
    """Map a scraped fund row (``{date, close}``) to the OHLCV model shape.

    A fund publishes a single NAV per day, so ``open == high == low == close``
    and ``volume`` is ``0`` (no executed volume on the secondary NAV).
    """
    close = row["close"]
    return {
        "date": row["date"],
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": 0,
    }