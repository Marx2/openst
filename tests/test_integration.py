import pytest
from src.openbb_client import get_dividend_yield, get_dividend_history, get_price_history

pytestmark = pytest.mark.integration


def test_snps_yield_is_zero():
    """SNPS does not pay a dividend — expect 0.0."""
    result = get_dividend_yield("SNPS")
    assert result == 0.0


def test_snps_history_is_empty():
    """SNPS does not pay a dividend — expect empty list."""
    result = get_dividend_history("SNPS")
    assert result == []


def test_aapl_yield_is_positive():
    """AAPL pays a dividend — expect positive float."""
    result = get_dividend_yield("AAPL")
    assert result is not None
    assert result > 0


def test_aapl_history_has_entries():
    """AAPL pays a dividend — expect non-empty list."""
    result = get_dividend_history("AAPL")
    assert result is not None
    assert len(result) > 0


@pytest.mark.integration
def test_aapl_price_history_nonempty():
    from datetime import date, timedelta
    end = date.today()
    result = get_price_history("AAPL", str(end - timedelta(days=365)), str(end))
    assert result is not None and len(result) > 0
