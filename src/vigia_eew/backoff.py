"""Exponential backoff with jitter (RF-03, RNF-03).

Pure helper reused by the WebSocket reconnection (`ingest/ws_emsc.py`) and by the
`Supervisor`'s task restarts. The strategy is *equal jitter*: the nominal wait
doubles (base·2^(attempt-1)) saturated at `cap`, and the jitter spreads the
result over `[nominal/2, nominal]` to avoid synchronized reconnections.
"""

from __future__ import annotations

import random
from collections.abc import Callable

# Default generator: a number in [0, 1). Injectable for deterministic tests.
_default_rng: Callable[[], float] = random.random


def exponential_backoff(
    attempt: int,
    *,
    base: float = 1.0,
    cap: float = 60.0,
    jitter: bool = True,
    rng: Callable[[], float] = _default_rng,
) -> float:
    """Computes the wait (in seconds) before the next retry.

    Args:
        attempt: attempt number, starting at 1.
        base: wait for the first attempt (attempt=1) without jitter.
        cap: maximum wait; saturates the exponential growth.
        jitter: if False, returns the deterministic nominal wait.
        rng: source of randomness in [0, 1); injectable in tests.

    Returns:
        Seconds to wait (always <= `cap`).

    Raises:
        ValueError: if `attempt` < 1.
    """
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    # 2.0 (not 2) so mypy infers float: `int ** int` can be float (negative exponents).
    nominal = min(cap, base * 2.0 ** (attempt - 1))
    if not jitter:
        return nominal
    # Equal jitter: fixed half + random half, bounded by `nominal` (<= cap).
    half = nominal / 2
    return half + rng() * half
