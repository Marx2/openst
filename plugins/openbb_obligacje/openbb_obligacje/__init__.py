"""obligacje.pl OpenBB provider extension — Polish retail savings bonds (D79).

The ``openbb_obligacje`` provider prices the eight Polish retail savings-bond
series (OTS, ROR, DOR, TOS, COI, ROS, EDO, ROD) on demand: the fetchers read
``openst.bond_series`` + ``openst.cpi_12m`` from Postgres and run the pure
pricing engine in :mod:`openbb_obligacje.engine`. There is no market price for
these instruments — the redemption value is computed from the issue parameters
and the 12-month CPI history.

The fetchre are registered under the *equity* model keys because OpenBB 4.7.x
ships no fixed-income price router or ``FixedIncomeHistorical`` standard model
(verified in the 19.6 notes) — the same overload the biznesradar plugin uses for
Catalyst bonds. They are therefore reachable as ``obb.equity.price.historical``,
``obb.equity.search`` and ``obb.equity.profile`` with ``provider="obligacje"``.
"""

from openbb_core.provider.abstract.provider import Provider

from openbb_obligacje.models.fixedincome_historical import FixedIncomeHistoricalFetcher
from openbb_obligacje.models.fixedincome_profile import FixedIncomeProfileFetcher
from openbb_obligacje.models.fixedincome_search import FixedIncomeSearchFetcher

obligacje_provider = Provider(
    name="obligacje",
    description=(
        "obligacjeskarbowe.pl retail savings bonds priced from issue parameters "
        "and CPI history (no market price exists)"
    ),
    fetcher_dict={
        "EquityHistorical": FixedIncomeHistoricalFetcher,
        "EquitySearch": FixedIncomeSearchFetcher,
        "EquityInfo": FixedIncomeProfileFetcher,
    },
)

__all__ = ["obligacje_provider"]