"""Helpers for coordinating startup timing."""

from math import ceil
from time import perf_counter


def remaining_delay_ms(
    started_at: float,
    minimum_seconds: float,
    now: float | None = None,
) -> int:
    """Return the remaining wait time needed to satisfy *minimum_seconds*."""
    if minimum_seconds <= 0:
        return 0

    current_time = perf_counter() if now is None else now
    elapsed = max(0.0, current_time - started_at)
    remaining = max(0.0, minimum_seconds - elapsed)
    if remaining == 0:
        return 0
    return ceil(remaining * 1000)
