"""obligacje.pl OpenBB provider extension — Polish retail savings bonds (D79).

The ``openbb_obligacje`` provider prices the eight Polish retail savings-bond
series (OTS, ROR, DOR, TOS, COI, ROS, EDO, ROD) on demand via the pure pricing
engine in :mod:`openbb_obligacje.engine`. There is no market price for these
instruments — the redemption value is computed from the issue parameters
(``openst.bond_series``) and the 12-month CPI history (``openst.cpi_12m``).

The fetcher stubs live in ``models/``; the DB-backed implementations land in
step 19.6. The engine (and its worked-example tests) is the source of truth for
the pricing math.
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
        "FixedIncomeHistorical": FixedIncomeHistoricalFetcher,
        "FixedIncomeSearch": FixedIncomeSearchFetcher,
        "FixedIncomeProfile": FixedIncomeProfileFetcher,
    },
)

__all__ = ["obligacje_provider"]