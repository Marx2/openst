"""Polish fund-category NAV history via analizy.pl — plan §72.39 step 2, stage 2.

Fixture-driven, with `httpx.get` mocked. The fixtures in
``tests/fixtures/analizy/`` are raw captured responses, so every assertion here
is against bytes the source actually served.

The assertions that matter are not the ones a clean parser passes by accident:

* the two proven dates reproduce **to the cent** (2023-04-13 -> 382.05,
  2026-08-19 -> 904.80). These are the two measurements the whole class-W
  investigation rests on; a provider that cannot reproduce them is wrong
  however tidy its tests look.
* currency is asserted as PLN **explicitly**, from the payload — a bare number
  with no currency is the mistake ``ticker_reference``'s empty ``yahoo_suffix``
  already caused once.
* the empty ``fund_with_dividend_*`` series is never selected.
* an unknown code (404) stays an error and does not collapse into "no history".
"""

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from src.openbb_client import (
    ANALIZY_EXPECTED_CURRENCY,
    UnknownFundCategory,
    get_fund_category_history,
)

FIXTURES = Path(__file__).parent / "fixtures" / "analizy"


def load_fixture(code: str) -> dict:
    return json.loads((FIXTURES / f"{code}.json").read_text(encoding="utf-8"))


def mock_get(payload: dict, status_code: int = 200):
    """Patch httpx.get to serve `payload`; record the URLs it was called with."""
    calls: list[str] = []

    def fake_get(url, **kwargs):
        calls.append(url)
        request = httpx.Request("GET", url)
        response = httpx.Response(status_code, json=payload, request=request)
        return response

    return patch("src.openbb_client.httpx.get", side_effect=fake_get), calls


# --- the gate: the two proven dates ---------------------------------------


def test_reproduces_both_proven_dates_to_the_cent():
    """The stage gate. Both dates the investigation rests on, from the fixture."""
    with mock_get(load_fixture("ING01W"))[0]:
        rows = get_fund_category_history("ING01W", "2023-01-01", "2026-12-31")

    by_date = {r["date"]: r["close"] for r in rows}
    assert by_date["2023-04-13"] == pytest.approx(382.05, abs=0.005)
    assert by_date["2026-08-19"] == pytest.approx(904.80, abs=0.005)


def test_w_series_ends_at_the_recorded_current_quote():
    """931.03 on 2026-09-29 — the reading that identified W as the class.

    Asserted separately from history because it is what makes the *valuation*
    correct rather than merely historically consistent.
    """
    with mock_get(load_fixture("ING01W"))[0]:
        rows = get_fund_category_history("ING01W", "2026-09-01", "2026-12-31")
    assert rows[-1] == {"date": "2026-09-29", "close": pytest.approx(931.03, abs=0.005)}


def test_class_a_fixture_still_reproduces_our_existing_bars():
    """ING01 yields 351.93 / 795.02 — the bars biznesradar already serves.

    Cross-check that the same endpoint carries both categories, so the ~12.7%
    class gap is a property of the source and not of our pipeline.
    """
    with mock_get(load_fixture("ING01"))[0]:
        rows = get_fund_category_history("ING01", "2023-01-01", "2026-12-31")
    by_date = {r["date"]: r["close"] for r in rows}
    assert by_date["2023-04-13"] == pytest.approx(351.93, abs=0.005)
    assert by_date["2026-08-19"] == pytest.approx(795.02, abs=0.005)


# --- currency --------------------------------------------------------------


@pytest.mark.parametrize("code", ["ING01", "ING01W", "ING04", "ING81", "ING92"])
def test_currency_is_pln_explicitly(code):
    """Every category here is PLN, and the source says so. Assert it, don't infer."""
    payload = load_fixture(code)
    with mock_get(payload)[0]:
        rows = get_fund_category_history(code, "2020-01-01", "2026-12-31")
    assert rows, f"{code} produced no rows"
    assert payload["currency"] == ANALIZY_EXPECTED_CURRENCY
    # The series carries its own currency too; that is what the client prefers.
    series = [s for s in payload["series"] if s["price"]][0]
    assert series["currency"] == ANALIZY_EXPECTED_CURRENCY


def test_refuses_a_payload_whose_currency_is_not_pln():
    """A bare number in the wrong currency must be refused, not passed on."""
    payload = load_fixture("ING01W")
    payload["currency"] = "EUR"
    for s in payload["series"]:
        s["currency"] = "EUR"
    with mock_get(payload)[0]:
        assert get_fund_category_history("ING01W", "2023-01-01", "2026-12-31") is None


def test_refuses_when_the_currency_is_absent_entirely():
    """No declared currency at all is the ticker_reference yahoo_suffix mistake."""
    payload = load_fixture("ING01W")
    payload.pop("currency", None)
    for s in payload["series"]:
        s.pop("currency", None)
    with mock_get(payload)[0]:
        assert get_fund_category_history("ING01W", "2023-01-01", "2026-12-31") is None


# --- the empty-series trap -------------------------------------------------


def test_selects_the_populated_series_not_the_first():
    """series[1] (`fund_with_dividend_*`) is empty on every fund.

    Selecting positionally would still work today, which is exactly why it needs
    a test: the fixture puts the populated series first, so a positional read
    passes by luck. Here the empty one leads.
    """
    payload = load_fixture("ING01W")
    payload["series"] = list(reversed(payload["series"]))
    assert payload["series"][0]["price"] == [], "fixture no longer leads with empty"

    with mock_get(payload)[0]:
        rows = get_fund_category_history("ING01W", "2023-01-01", "2026-12-31")
    assert rows, "empty dividend series was selected"
    by_date = {r["date"]: r["close"] for r in rows}
    assert by_date["2023-04-13"] == pytest.approx(382.05, abs=0.005)


def test_no_populated_series_is_an_empty_result_not_an_error():
    payload = load_fixture("ING01W")
    for s in payload["series"]:
        s["price"] = []
    with mock_get(payload)[0]:
        assert get_fund_category_history("ING01W", "2023-01-01", "2026-12-31") == []


# --- failure modes stay distinguishable ------------------------------------


def test_unknown_code_raises_rather_than_returning_empty():
    """404 upstream is a real error. Collapsing it to [] is what this stage exists
    to prevent: `200` with zero bars is the shape a *dead* provider returns."""
    with mock_get({"success": False}, status_code=404)[0]:
        with pytest.raises(UnknownFundCategory):
            get_fund_category_history("ING01A", "2023-01-01", "2026-12-31")


def test_empty_code_raises():
    with pytest.raises(UnknownFundCategory):
        get_fund_category_history("  ", "2023-01-01", "2026-12-31")


def test_server_error_returns_none_so_the_route_can_negative_cache():
    with mock_get({"error": "boom"}, status_code=500)[0]:
        assert get_fund_category_history("ING01W", "2023-01-01", "2026-12-31") is None


def test_transport_failure_returns_none():
    def boom(url, **kwargs):
        raise httpx.ConnectError("no route to host")

    with patch("src.openbb_client.httpx.get", side_effect=boom):
        assert get_fund_category_history("ING01W", "2023-01-01", "2026-12-31") is None


def test_non_json_body_returns_none():
    request = httpx.Request("GET", "https://www.analizy.pl/api/quotation/fio/ING01W")
    response = httpx.Response(200, text="<html>maintenance</html>", request=request)
    with patch("src.openbb_client.httpx.get", return_value=response):
        assert get_fund_category_history("ING01W", "2023-01-01", "2026-12-31") is None


# --- request shape ---------------------------------------------------------


def test_requests_the_providers_own_code_and_upper_cases_it():
    patcher, calls = mock_get(load_fixture("ING01W"))
    with patcher:
        get_fund_category_history("ing01w", "2023-01-01", "2026-12-31")
    assert calls == ["https://www.analizy.pl/api/quotation/fio/ING01W"]


def test_date_window_is_inclusive_at_both_ends():
    with mock_get(load_fixture("ING01W"))[0]:
        rows = get_fund_category_history(
            "ING01W", "2023-04-13", "2026-08-19"
        )
    assert rows[0]["date"] == "2023-04-13"
    assert rows[-1]["date"] == "2026-08-19"


def test_rows_are_ascending_by_date():
    with mock_get(load_fixture("ING01W"))[0]:
        rows = get_fund_category_history("ING01W", "2019-01-01", "2026-12-31")
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates)
    assert len(dates) == len(set(dates)), "duplicate dates in the series"


def test_window_outside_the_category_window_is_empty_not_an_error():
    """W starts 2019-06-10 (its inception). Asking for 2018 is empty, not a 404."""
    with mock_get(load_fixture("ING01W"))[0]:
        assert get_fund_category_history("ING01W", "2018-01-01", "2018-12-31") == []


def test_skips_malformed_points_rather_than_emitting_nones():
    payload = load_fixture("ING01W")
    price = [s for s in payload["series"] if s["price"]][0]["price"]
    # Pick a date the real series does not carry (a weekend), so a skipped
    # malformed entry is observable as an absence rather than shadowed by a
    # genuine point.
    absent = next(d for d in ("2023-04-09", "2023-04-08") if d not in
                  {p["date"] for p in price})
    price.insert(0, {"date": absent, "value": None})
    price.insert(0, {"value": 1.0})
    price.insert(0, {"date": absent, "value": "not-a-number"})

    with mock_get(payload)[0]:
        rows = get_fund_category_history("ING01W", "2023-04-01", "2023-04-13")

    assert all(r["close"] is not None for r in rows)
    assert all(isinstance(r["date"], str) for r in rows)
    by_date = {r["date"]: r["close"] for r in rows}
    assert absent not in by_date, "a malformed point was emitted"
    # The genuine points either side survive untouched.
    assert by_date["2023-04-13"] == pytest.approx(382.05, abs=0.005)
    assert by_date["2023-04-12"] == pytest.approx(377.30, abs=0.005)


def test_a_malformed_point_does_not_shadow_the_real_point_for_that_date():
    """A duplicate date with an unusable value must not blank the good one.

    This is the regression that matters: the filter runs per point, so a bad
    entry is dropped on its own merits rather than removing the date.
    """
    payload = load_fixture("ING01W")
    price = [s for s in payload["series"] if s["price"]][0]["price"]
    price.insert(0, {"date": "2023-04-12", "value": None})

    with mock_get(payload)[0]:
        rows = get_fund_category_history("ING01W", "2023-04-12", "2023-04-12")

    assert rows == [{"date": "2023-04-12", "close": pytest.approx(377.30, abs=0.005)}]


# --- every captured code parses -------------------------------------------


@pytest.mark.parametrize("code", ["ING01", "ING01W", "ING04", "ING81", "ING82", "ING88", "ING92"])
def test_every_captured_fixture_parses(code):
    with mock_get(load_fixture(code))[0]:
        rows = get_fund_category_history(code, "2000-01-01", "2026-12-31")
    assert rows, f"{code} produced no rows"
    assert all(r["close"] > 0 for r in rows)
