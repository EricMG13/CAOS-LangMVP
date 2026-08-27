"""Relative-value signal bands (ported from LEGACY artifacts/relative_value.py).

The metric registry owns thresholds and polarity — a spread's sign alone has no
credit meaning, and the system signal is separate from the Analyst
recommendation matrix.
"""

from __future__ import annotations

import math

from ..contracts import SystemSignal


def signal_for_spread(spread_bps: float | None) -> SystemSignal | None:
    if spread_bps is None or not math.isfinite(spread_bps):
        return None
    if spread_bps <= 350:
        return SystemSignal.ATTRACTIVE
    if spread_bps <= 500:
        return SystemSignal.FAIR
    return SystemSignal.UNATTRACTIVE
