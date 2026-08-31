"""Tests for TokenBucket rate limiting and exponential-backoff retry."""
from __future__ import annotations

import time

from app.rate_limit import TokenBucket, retry_with_backoff


def _clock_and_sleeper():
    clock = {"t": 1000.0}
    sleeps: list[float] = []

    def now() -> float:
        return clock["t"]

    def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        clock["t"] += seconds

    return clock, sleeps, now, sleeper


def test_bucket_allows_burst_up_to_capacity():
    _clock, sleeps, now, sleeper = _clock_and_sleeper()
    bucket = TokenBucket(rate=1.0, capacity=5.0, now=now, sleeper=sleeper)
    for _ in range(5):
        bucket.consume(1.0)
    assert sleeps == []


def test_bucket_throttles_beyond_capacity():
    _clock, sleeps, now, sleeper = _clock_and_sleeper()
    bucket = TokenBucket(rate=2.0, capacity=1.0, now=now, sleeper=sleeper)
    bucket.consume(1.0)
    bucket.consume(1.0)
    assert len(sleeps) == 1
    assert abs(sleeps[0] - 0.5) < 1e-6


def test_bucket_refills_over_time():
    clock, sleeps, now, sleeper = _clock_and_sleeper()
    bucket = TokenBucket(rate=1.0, capacity=1.0, now=now, sleeper=sleeper)
    bucket.consume(1.0)
    clock["t"] += 0.5  # half a token refilled
    bucket.consume(1.0)
    assert len(sleeps) == 1
    assert abs(sleeps[0] - 0.5) < 1e-6


def test_retry_succeeds_after_transient_failures():
    attempts = {"n": 0}
    sleeps: list[float] = []

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise TimeoutError("transient")
        return "ok"

    result = retry_with_backoff(
        flaky,
        retries=3,
        base_delay=0.01,
        sleeper=sleeps.append,
    )
    assert result == "ok"
    assert attempts["n"] == 3
    assert len(sleeps) == 2


def test_retry_respects_should_retry_false():
    attempts = {"n": 0}

    def always_fail():
        attempts["n"] += 1
        raise ValueError("no retry")

    with __import__("pytest").raises(ValueError):
        retry_with_backoff(
            always_fail,
            retries=3,
            base_delay=0.01,
            should_retry=lambda exc: isinstance(exc, TimeoutError),
            sleeper=lambda _s: None,
        )
    assert attempts["n"] == 1


def test_retry_exhausts_and_raises_last_error():
    attempts = {"n": 0}

    def always_fail():
        attempts["n"] += 1
        raise TimeoutError("boom")

    with __import__("pytest").raises(TimeoutError):
        retry_with_backoff(
            always_fail,
            retries=2,
            base_delay=0.01,
            sleeper=lambda _s: None,
        )
    assert attempts["n"] == 3


def test_retry_backoff_caps_delay():
    attempts = {"n": 0}

    def always_fail():
        attempts["n"] += 1
        raise TimeoutError("boom")

    sleeps: list[float] = []
    with __import__("pytest").raises(TimeoutError):
        retry_with_backoff(
            always_fail,
            retries=5,
            base_delay=1.0,
            max_delay=2.0,
            sleeper=sleeps.append,
        )
    assert attempts["n"] == 6
    assert all(s <= 2.0 + 0.25 for s in sleeps)
