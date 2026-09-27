"""JSON serialization safety.

Regression cover for the mechanism whose absence let two real bugs ship: a
``-Infinity`` cell anywhere in a payload produced ``{"low": -null}`` (invalid
JSON, rejecting the whole document), and the word "NaN"/"Infinity" inside any
*string* was rewritten to "null". Both came from regex-post-processing the
serialized text; the fix sanitizes the object graph instead.
"""

import json
import math

import pytest

from src import jsonio
from src.jsonio import dumps, json_safe


def _roundtrip(value):
    """Serialize then parse — the property every caller of dumps() relies on."""
    return json.loads(dumps(value))


# --- non-finite floats -----------------------------------------------------


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_floats_become_null(value):
    assert _roundtrip({"x": value}) == {"x": None}


def test_negative_infinity_produces_parseable_json():
    """The exact bug: -Infinity became -null, so json.loads raised on the whole body.

    json.dumps writes -Infinity with no quotes, and a naive ``\\bInfinity\\b``
    pass rewrites the Infinity inside it, leaving a stray minus sign.
    """
    payload = {"rows": [{"low": float("-inf")}, {"low": 1.5}]}
    parsed = _roundtrip(payload)
    assert parsed == {"rows": [{"low": None}, {"low": 1.5}]}


def test_mixed_finite_and_non_finite_in_one_payload():
    payload = {"nan": float("nan"), "inf": float("inf"), "ninf": float("-inf"), "ok": 1.25}
    assert _roundtrip(payload) == {"nan": None, "inf": None, "ninf": None, "ok": 1.25}


def test_non_finite_nested_deeply():
    # Tuples normalize to lists on the way through — json_safe rebuilds containers.
    payload = {"a": [{"b": ({"c": [float("-inf"), float("nan")]},)}]}
    assert _roundtrip(payload) == {"a": [{"b": [{"c": [None, None]}]}]}


def test_ordinary_numbers_survive_untouched():
    payload = {"z": 0, "i": -5, "f": 1.5, "neg": -0.0, "big": 1e300, "small": 1e-300}
    assert _roundtrip(payload) == payload


def test_nan_inside_a_nested_list_of_floats():
    assert _roundtrip([1.0, float("nan"), 2.0]) == [1.0, None, 2.0]


# --- strings must never be rewritten ---------------------------------------


@pytest.mark.parametrize("text", [
    "NaN Technologies",
    "Infinity Ltd wins",
    "-Infinity",
    "NaN",
    "Infinity",
    "company called NaNNA",
])
def test_strings_containing_nan_or_infinity_are_preserved(text):
    assert _roundtrip({"name": text}) == {"name": text}


def test_headline_containing_the_words_survives():
    """News headlines and company names flow through this path verbatim."""
    rows = [{"title": "Infinity Pharma shares surge"}, {"name": "NaN Holdings"}]
    assert _roundtrip(rows) == rows


def test_string_keys_are_untouched():
    assert _roundtrip({"NaN": 1, "Infinity": 2}) == {"NaN": 1, "Infinity": 2}


# --- json_safe contract ----------------------------------------------------


def test_json_safe_returns_none_for_non_finite():
    assert json_safe(float("-inf")) is None
    assert json_safe(float("nan")) is None


def test_json_safe_passes_through_non_floats():
    obj = object()
    assert json_safe("s") == "s"
    assert json_safe(7) == 7
    assert json_safe(None) is None
    assert json_safe(obj) is obj


def test_json_safe_converts_tuples_to_lists():
    assert json_safe((1, 2)) == [1, 2]


def test_json_safe_does_not_mutate_the_input():
    payload = {"x": float("nan"), "rows": [{"y": float("inf")}]}
    json_safe(payload)
    assert math.isnan(payload["x"])
    assert math.isinf(payload["rows"][0]["y"])


# --- other value shapes ----------------------------------------------------


def test_unserializable_objects_are_coerced_not_raised():
    from decimal import Decimal

    assert _roundtrip({"d": Decimal("1.5")}) == {"d": "1.5"}


def test_output_is_utf8_not_escaped():
    assert "ą" in dumps({"name": "łąk"})


def test_dumps_is_a_thin_single_implementation():
    """main.py's response class and cache path must not re-grow their own copy."""
    assert jsonio.dumps({"a": float("nan")}) == '{"a": null}'
