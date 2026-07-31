"""Agent 任务并行调度冒烟（不启浏览器）。"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def test_dispatch_workers_overlap():
    lock = threading.Lock()
    active = 0
    peak = 0

    def work(_i: int) -> None:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1

    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = [pool.submit(work, i) for i in range(8)]
        for fut in as_completed(futs):
            fut.result()

    assert peak >= 3
    assert peak <= 5
