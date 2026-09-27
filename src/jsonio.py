"""JSON serialization that never emits invalid JSON and never corrupts strings.

pandas hands us non-finite floats (``NaN`` from a missing bar, ``-inf`` from a
computed spread). ``json.dumps`` writes those as bare ``NaN``/``Infinity``/
``-Infinity``, which are JavaScript literals, not JSON — every strict client
parser rejects the whole document.

The previous implementation regex-post-processed the serialized string::

    re.sub(r'\\bNaN\\b', 'null', raw)
    re.sub(r'\\bInfinity\\b', 'null', raw)
    re.sub(r'\\b-Infinity\\b', 'null', raw)

which was wrong twice over:

* ``\\bInfinity\\b`` matches the ``Infinity`` inside ``-Infinity`` (``-`` is a
  non-word char, so there is a boundary before ``I``), turning ``-Infinity``
  into ``-null`` — itself invalid JSON. The ``-Infinity`` rule then never fires
  because the text no longer exists. A single negative-infinity cell anywhere in
  a payload broke the entire response.
* The patterns cannot tell code from data, so a *string* containing the word was
  rewritten too: ``"NaN Technologies"`` became ``"null Technologies"``, as did
  any news headline or bond name containing "Infinity".

Sanitizing the object graph instead of the output text fixes both: strings are
never inspected, and non-finite floats are replaced wherever they are nested.
"""

from __future__ import annotations

import json
import math
from typing import Any


def json_safe(value: Any) -> Any:
    """Return ``value`` with every non-finite float replaced by ``None``.

    Recurses through dicts and lists. Anything else is returned untouched, so
    strings pass through byte-for-byte.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def dumps(value: Any) -> str:
    """Serialize to a JSON string that is always parseable.

    ``default=str`` keeps the previous behaviour of coercing an unexpected object
    (a Decimal, a Timestamp) rather than raising, and ``allow_nan=True`` remains
    a last-resort net: ``json_safe`` has already removed every non-finite float,
    so this path should be unreachable, and reaching it would have degraded
    output rather than failed the request.
    """
    return json.dumps(json_safe(value), ensure_ascii=False, allow_nan=True, default=str)
