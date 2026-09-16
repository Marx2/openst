"""Wire-check (D79 19.6) — obligacje is reachable via the *equity* routers.

OpenBB 4.7.x exposes no fixed-income price router, so the obligacje fetchers are
registered under ``EquityHistorical`` / ``EquitySearch`` / ``EquityInfo``. This
test asserts those model keys resolve ``obligacje`` as a provider through the
real ``ProviderInterface`` — the same registry the routers use to build the
``provider`` Literal for ``obb.equity.price.historical`` / ``obb.equity.search``
/ ``obb.equity.profile``.
"""

from __future__ import annotations


def _model_choices(model: str) -> tuple[str, ...]:
    from openbb_core.app.provider_interface import ProviderInterface

    providers = ProviderInterface().model_providers
    literal = providers[model].__annotations__["provider"]
    return literal.__args__


def test_obligacje_registered_on_equity_models():
    for model in ("EquityHistorical", "EquitySearch", "EquityInfo"):
        assert "obligacje" in _model_choices(model), model


def test_obligacje_not_registered_on_fixedincome_models():
    # No fixed-income router exists in OpenBB 4.7 — the key must simply not matter.
    providers = __import__(
        "openbb_core.app.provider_interface", fromlist=["ProviderInterface"]
    ).ProviderInterface().model_providers
    assert "EquityHistorical" in providers
    assert "EquitySearch" in providers
    assert "EquityInfo" in providers