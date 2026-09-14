"""TFI/FIZ open-end fund table parser — 2-column Data|Kurs (D77 16.4).

Column indices (confirmed from ``tests/fixtures/biznesradar/NNEP25.TFI.html``):
``{date: 0, close: 1}``.
"""

FUND_COLUMNS = {"date": 0, "close": 1}


def parse_fund_row(row: tuple[str, str]) -> dict:
    """Map a 2-column (Data, Kurs) row to an EquityHistorical-shaped dict."""
    raise NotImplementedError  # implemented in 16.4