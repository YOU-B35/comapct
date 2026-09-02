import unittest
from unittest.mock import MagicMock, patch

from agent.handlers import handle_amazon_sync, handle_amazon_write
from app.observability.task_timing import finish_task_timing, record_duration, start_task_timing


class AmazonTaskTimingContextTests(unittest.TestCase):
    def test_sync_nested_worker_contributes_to_task_timing(self):
        timing, token = start_task_timing("amazon_sync", "amazon-sync-1")
        client = MagicMock()
        task = {
            "task_id": "amazon-sync-1",
            "payload": {"scope": "daily", "browser_id": "browser-1"},
        }

        def crawl(**_kwargs):
            record_duration("amazon_home.open", 0.25)
            return {"result_summary": {}}

        with patch("agent.handlers.crawl_amazon", side_effect=crawl):
            handle_amazon_sync(client, task)

        payload = finish_task_timing(timing, token, outcome="handled")
        self.assertEqual(payload["stages_ms"]["amazon_home.open"], 250)

    def test_write_nested_worker_contributes_to_task_timing(self):
        timing, token = start_task_timing("amazon_write", "amazon-write-1")
        client = MagicMock()
        task = {
            "task_id": "amazon-write-1",
            "payload": {"action": "update_price", "browser_id": "browser-1"},
        }

        def write(**_kwargs):
            record_duration("amazon_write.request", 0.1)
            return {"ok": True}

        with patch("agent.handlers.execute_amazon_write", side_effect=write):
            handle_amazon_write(client, task)

        payload = finish_task_timing(timing, token, outcome="handled")
        self.assertEqual(payload["stages_ms"]["amazon_write.request"], 100)


if __name__ == "__main__":
    unittest.main()
