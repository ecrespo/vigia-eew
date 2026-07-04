"""Tests for exponential backoff with jitter (RF-03, RNF-03)."""

from __future__ import annotations

import pytest

from vigia_eew.backoff import exponential_backoff


def test_sequence_without_jitter():
    # Without jitter, the wait doubles: 1, 2, 4, 8 s (base=1).
    assert exponential_backoff(1, base=1.0, cap=60.0, jitter=False) == 1.0
    assert exponential_backoff(2, base=1.0, cap=60.0, jitter=False) == 2.0
    assert exponential_backoff(3, base=1.0, cap=60.0, jitter=False) == 4.0
    assert exponential_backoff(4, base=1.0, cap=60.0, jitter=False) == 8.0


def test_saturates_at_the_cap():
    # base*2^(attempt-1) would grow unbounded; it saturates at `cap`.
    assert exponential_backoff(7, base=1.0, cap=60.0, jitter=False) == 60.0
    assert exponential_backoff(20, base=1.0, cap=60.0, jitter=False) == 60.0


def test_jitter_bounded_between_half_and_full():
    # Equal jitter: result in [capped/2, capped]. attempt=4 -> capped=8.
    assert exponential_backoff(4, base=1.0, cap=60.0, rng=lambda: 0.0) == 4.0
    assert exponential_backoff(4, base=1.0, cap=60.0, rng=lambda: 1.0) == 8.0
    half = exponential_backoff(4, base=1.0, cap=60.0, rng=lambda: 0.5)
    assert half == 6.0


def test_jitter_never_exceeds_the_cap():
    # Even with rng=1.0 at high attempts, `cap` is never exceeded.
    assert exponential_backoff(30, base=1.0, cap=60.0, rng=lambda: 1.0) == 60.0


def test_invalid_attempt():
    with pytest.raises(ValueError):
        exponential_backoff(0)
