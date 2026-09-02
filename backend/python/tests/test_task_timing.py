from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from io import StringIO
import json
import unittest
from unittest.mock import patch

from app.observability.task_timing import finish_task_timing, record_duration, start_task_timing
from agent.browser_lock_pool import BrowserLockPool


class TaskTimingTest(unittest.TestCase):
    def test_finish_emits_stage_summary(self) -> None:
        timing, token = start_task_timing("temu_crawl", "task-1")
        record_duration("browser_launch.temu", 0.123)

        with patch("sys.stdout", new_callable=StringIO) as output:
            payload = finish_task_timing(timing, token, outcome="handled")

        self.assertEqual(payload["task_type"], "temu_crawl")
        self.assertEqual(payload["stages_ms"], {"browser_launch.temu": 123})
        event = json.loads(output.getvalue().removeprefix("[CrawlPerf] "))
        self.assertEqual(event["outcome"], "handled")

    def test_browser_lock_wait_is_recorded_for_active_task(self) -> None:
        timing, token = start_task_timing("pdd_sync", "task-2")
        pool = BrowserLockPool()

        with pool.guard("pdd", "pdd:1:store-a"):
            pass
        payload = finish_task_timing(timing, token, outcome="handled")

        self.assertIn("browser_lock_wait.pdd", payload["stages_ms"])

    def test_child_thread_contexts_contribute_to_one_task_summary(self) -> None:
        timing, token = start_task_timing("temu_crawl", "task-3")

        def record_from_child() -> None:
            record_duration("temu_api.request", 0.01)

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(copy_context().run, record_from_child) for _ in range(8)]
            for future in futures:
                future.result()

        payload = finish_task_timing(timing, token, outcome="handled")
        self.assertEqual(payload["stages_ms"]["temu_api.request"], 80)


if __name__ == "__main__":
    unittest.main()
