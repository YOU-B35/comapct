"""Low-overhead task timing that works across the synchronous crawler stack."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
import json
import time
from threading import Lock
from typing import Iterator


@dataclass
class TaskTiming:
    task_type: str
    task_id: str
    started_at: float = field(default_factory=time.perf_counter)
    stages_ms: dict[str, int] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, repr=False)


_CURRENT_TIMING: ContextVar[TaskTiming | None] = ContextVar("crawl_task_timing", default=None)


def start_task_timing(task_type: str, task_id: str) -> tuple[TaskTiming, Token[TaskTiming | None]]:
    timing = TaskTiming(task_type=task_type or "unknown", task_id=task_id or "unknown")
    return timing, _CURRENT_TIMING.set(timing)


def record_duration(stage: str, seconds: float) -> None:
    timing = _CURRENT_TIMING.get()
    if timing is None:
        return
    milliseconds = max(0, int(seconds * 1000))
    with timing._lock:
        timing.stages_ms[stage] = timing.stages_ms.get(stage, 0) + milliseconds


@contextmanager
def timed_stage(stage: str) -> Iterator[None]:
    started_at = time.perf_counter()
    try:
        yield
    finally:
        record_duration(stage, time.perf_counter() - started_at)


def finish_task_timing(
    timing: TaskTiming,
    token: Token[TaskTiming | None],
    *,
    outcome: str,
) -> dict[str, object]:
    try:
        with timing._lock:
            stages_ms = dict(sorted(timing.stages_ms.items()))
        payload: dict[str, object] = {
            "event": "crawl_task_timing",
            "task_type": timing.task_type,
            "task_id": timing.task_id,
            "outcome": outcome,
            "total_ms": max(0, int((time.perf_counter() - timing.started_at) * 1000)),
            "stages_ms": stages_ms,
        }
        print(f"[CrawlPerf] {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}", flush=True)
        return payload
    finally:
        _CURRENT_TIMING.reset(token)
