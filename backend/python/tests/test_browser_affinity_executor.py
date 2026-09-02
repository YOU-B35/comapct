import threading
import time
import unittest

from agent.task_executor import BrowserAffinityTaskExecutor


def _task(task_type: str, tenant_id: int, session_key: str | None = None) -> dict:
    payload = {"tenant_id": tenant_id}
    if session_key is not None:
        payload["session_key"] = session_key
    return {"task_type": task_type, "payload": payload}


class BrowserAffinityTaskExecutorTests(unittest.TestCase):
    def test_same_temu_browser_identity_runs_on_one_thread(self):
        seen: list[int] = []

        def run(_client, _task):
            seen.append(threading.get_ident())

        with BrowserAffinityTaskExecutor(max_workers=3) as executor:
            first = executor.submit(run, object(), _task("temu_login_open", 7, "shop-a"))
            second = executor.submit(run, object(), _task("temu_crawl", 7, "shop-a"))
            first.result(timeout=2)
            second.result(timeout=2)

        self.assertEqual(len(set(seen)), 1)

    def test_different_temu_sessions_keep_independent_stable_lanes(self):
        executor = BrowserAffinityTaskExecutor(max_workers=3)
        try:
            first_task = _task("temu_crawl", 7, "shop-a")
            second_task = _task("temu_crawl", 7, "shop-b")
            self.assertEqual(
                executor._lane_index((object(), first_task)),
                executor._lane_index((object(), first_task)),
            )
            self.assertEqual(
                executor._lane_index((object(), second_task)),
                executor._lane_index((object(), second_task)),
            )
            self.assertNotEqual(
                executor._lane_index((object(), first_task)),
                executor._lane_index((object(), second_task)),
            )
        finally:
            executor.shutdown()

    def test_multi_session_temu_task_uses_general_balancing(self):
        executor = BrowserAffinityTaskExecutor(max_workers=3)
        task = {
            "task_type": "temu_crawl",
            "payload": {
                "tenant_id": 7,
                "seller_sessions": [{"session_key": "shop-a"}, {"session_key": "shop-b"}],
            },
        }
        try:
            self.assertNotIn("temu:7:shop-a", executor._key_lanes)
            executor._lane_index((object(), task))
            self.assertEqual(executor._key_lanes, {})
        finally:
            executor.shutdown()

    def test_total_running_tasks_stays_within_worker_budget(self):
        lock = threading.Lock()
        active = 0
        peak = 0

        def run(_client, _task):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.05)
            with lock:
                active -= 1

        with BrowserAffinityTaskExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(run, object(), _task("amazon_sync", index))
                for index in range(9)
            ]
            for future in futures:
                future.result(timeout=2)

        self.assertGreaterEqual(peak, 2)
        self.assertLessEqual(peak, 3)


if __name__ == "__main__":
    unittest.main()
