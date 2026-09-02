"""Thread-affine task dispatch for Playwright-backed agent work.

Playwright's synchronous API binds browser objects to the thread that created
them.  The regular ``ThreadPoolExecutor`` may run two sequential tasks for the
same store on different threads, which makes a cached browser runtime unsafe.
This executor keeps a bounded set of single-thread lanes: Temu tasks for one
browser identity always use the same lane, while other tasks are balanced
across the same worker budget.
"""
from __future__ import annotations

import itertools
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable

from agent.browser_lock_pool import task_browser_keys


class BrowserAffinityTaskExecutor:
    """Bounded executor with a stable lane for each single-session Temu task."""

    def __init__(self, *, max_workers: int, thread_name_prefix: str = "agent-task") -> None:
        self._max_workers = max(1, int(max_workers))
        self._lanes = [
            ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"{thread_name_prefix}-{index}")
            for index in range(self._max_workers)
        ]
        self._round_robin = itertools.count()
        self._key_lanes: dict[str, int] = {}
        self._lane_key_counts = [0] * self._max_workers

    def __enter__(self) -> "BrowserAffinityTaskExecutor":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.shutdown(wait=True)

    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future:
        """Submit work using a stable lane when the last argument is an agent task."""
        return self._lanes[self._lane_index(args)].submit(fn, *args, **kwargs)

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        for lane in self._lanes:
            lane.shutdown(wait=wait, cancel_futures=cancel_futures)

    def _lane_index(self, args: tuple[Any, ...]) -> int:
        task = args[-1] if args and isinstance(args[-1], dict) else None
        if not isinstance(task, dict):
            return next(self._round_robin) % self._max_workers

        task_type = str(task.get("task_type") or "")
        if not task_type.startswith("temu_"):
            return next(self._round_robin) % self._max_workers

        keys = task_browser_keys("temu", task)
        if len(keys) != 1:
            return next(self._round_robin) % self._max_workers

        key = keys[0]
        lane = self._key_lanes.get(key)
        if lane is None:
            # Keep store identities evenly spread over the fixed worker budget.
            # Once assigned, a store never changes lanes during this process.
            lane = min(range(self._max_workers), key=lambda index: self._lane_key_counts[index])
            self._key_lanes[key] = lane
            self._lane_key_counts[lane] += 1
        return lane
