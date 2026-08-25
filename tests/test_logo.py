import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, "src")

from src import openbb_client
from src.openbb_client import get_logo


@pytest.fixture(autouse=True)
def clear_state():
    openbb_client._provider_blocked_until.clear()
    yield


def _profile_row(**fields):
    row = MagicMock()
    row.get = lambda k, default=None: fields.get(k, default)
    df = MagicMock()
    df.empty = False
    df.__getitem__ = lambda self, i: row if i == 0 else None
    df.iloc = {0: row}
    return df


class TestGetLogo:
    @patch("src.openbb_client.httpx.head")
    def test_fmp_hit_short_circuits(self, head):
        head.return_value = MagicMock(status_code=200)

        result = get_logo("aapl")

        assert result == {
            "source": "fmp",
            "remote_url": "https://images.financialmodelingprep.com/symbol/AAPL.png",
        }
        head.assert_called_once()

    @patch("src.openbb_client.obb")
    @patch("src.openbb_client.httpx.head")
    def test_falls_back_to_profile_website_favicon(self, head, mock_obb):
        head.return_value = MagicMock(status_code=404)
        mock_obb.equity.profile.return_value.to_df.return_value = _profile_row(
            company_url="https://investors.example.com/about"
        )

        result = get_logo("KTY.WA")

        assert result == {
            "source": "favicon",
            "remote_url": "https://www.google.com/s2/favicons?domain=investors.example.com&sz=128",
        }

    @patch("src.openbb_client.obb")
    @patch("src.openbb_client.httpx.head")
    def test_chain_exhausted_returns_none(self, head, mock_obb):
        head.return_value = MagicMock(status_code=404)
        mock_obb.equity.profile.side_effect = Exception("results not found")

        assert get_logo("NOPE") is None

    @patch("src.openbb_client.obb")
    @patch("src.openbb_client.httpx.head")
    def test_blocks_rate_limited_provider(self, head, mock_obb):
        head.return_value = MagicMock(status_code=404)
        mock_obb.equity.profile.side_effect = Exception("402 premium quota")

        get_logo("XYZ")

        assert openbb_client._provider_is_blocked("yfinance")

    @patch("src.openbb_client.obb")
    @patch("src.openbb_client.httpx.head")
    def test_head_exception_continues_to_profile(self, head, mock_obb):
        head.side_effect = Exception("connection error")
        mock_obb.equity.profile.return_value.to_df.return_value = _profile_row(
            company_url="https://example.com"
        )

        result = get_logo("AAPL")

        assert result == {
            "source": "favicon",
            "remote_url": "https://www.google.com/s2/favicons?domain=example.com&sz=128",
        }
