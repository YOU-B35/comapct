"""Token-bucket rate limiting and exponential-backoff retry helpers."""
from __future__ import annotations

import random
import threading
import time
from typing import Callable


def _now_default() -> float:
    return time.time()


class TokenBucket:
    """Process-local token bucket. ``consume`` blocks until tokens are available."""

    def __init__(
        self,
        rate: float,
        capacity: float,
        *,
        now: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self.rate = max(float(rate), 1e-9)
        self.capacity = max(float(capacity), 0.0)
        self._now = now or _now_default
        self._sleep = sleeper or time.sleep
        self._tokens = self.capacity
        self._last = self._now()
        self._lock = threading.Lock()

    def consume(self, tokens: float = 1.0) -> None:
        tokens = max(float(tokens), 0.0)
        with self._lock:
            while True:
                now = self._now()
                elapsed = max(0.0, now - self._last)
                self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
                self._last = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                self._sleep((tokens - self._tokens) / self.rate)


def retry_with_backoff(
    fn: Callable[[], object],
    *,
    retries: int = 2,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    should_retry: Callable[[Exception], bool] | None = None,
    sleeper: Callable[[float], None] | None = None,
):
    """Run ``fn`` with exponential backoff; raise the last error when exhausted."""
    sleep = sleeper or time.sleep
    attempts = max(0, int(retries)) + 1
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt + 1 >= attempts:
                break
            if should_retry is not None and not should_retry(exc):
                break
            delay = min(max_delay, base_delay * (2 ** attempt)) + random.uniform(
                0, 0.25 * base_delay
            )
            sleep(delay)
    assert last_exc is not None
    raise last_exc
