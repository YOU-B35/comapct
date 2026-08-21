import unittest
from unittest.mock import patch

from agent.handlers import handle_1688_monitor_crawl


class FakeClient:
    def __init__(self):
        self.ingested = None
        self.completed = None

    def ingest_1688_monitor(self, payload):
        self.ingested = payload
        return {"snapshot_id": "ms_x", "product_count": len(payload["products"]), "signal_count": 2}

    def complete_task_with_retry(self, task_id, *, status, result=None, error_code=None, error_message=None):
        self.completed = {
            "task_id": task_id,
            "status": status,
            "result": result,
            "error_code": error_code,
            "error_message": error_message,
        }


def _collector_payload():
    return {
        "platform": "1688",
        "snapshot_at": "2026-08-21 12:00:00",
        "products": [
            {
                "offer_id": "930671411701",
                "title": "KRANK HOOK",
                "price": "0.5",
                "total_sales": 100000,
                "rank": 1,
                "url": "https://detail.1688.com/offer/930671411701.html",
                "image_url": "https://cbu01.alicdn.com/example.jpg",
                "shop_name": "dongborui",
                "is_pinned": 1,
            }
        ],
        "shop": {},
        "meta": {},
    }


class Alibaba1688MonitorHandlerTest(unittest.TestCase):
    def test_handler_crawls_and_ingests(self):
        client = FakeClient()
        with patch(
            "app.platforms.alibaba1688_monitor_adapter.crawl_shop",
            return_value=_collector_payload(),
        ):
            handle_1688_monitor_crawl(
                client,
                {
                    "task_id": "agt_t1",
                    "payload": {
                        "tenant_id": 5,
                        "target_id": "mt_1",
                        "job_id": "mj_1",
                        "target_url": "https://shop16yx1905b2433.1688.com",
                        "crawl_strategy": "1688_shop_topn",
                        "config_json": '{"top_n":20,"pinned_offer_ids":["930671411701"]}',
                        "top_n": 20,
                    },
                },
            )
        self.assertEqual(client.ingested["target_id"], "mt_1")
        self.assertEqual(client.ingested["job_id"], "mj_1")
        self.assertEqual(client.ingested["products"][0]["product_id"], "930671411701")
        self.assertEqual(client.ingested["products"][0]["total_sales"], 100000)
        self.assertEqual(client.completed["status"], "success")
        self.assertEqual(client.completed["task_id"], "agt_t1")
        self.assertEqual(client.completed["result"]["snapshot_id"], "ms_x")

    def test_handler_fails_task_on_error(self):
        client = FakeClient()
        with patch(
            "app.platforms.alibaba1688_monitor_adapter.crawl_shop",
            side_effect=RuntimeError("MONITOR_AUTH_REQUIRED: not logged in"),
        ):
            handle_1688_monitor_crawl(
                client,
                {
                    "task_id": "agt_t2",
                    "payload": {"tenant_id": 5, "target_id": "mt_1", "target_url": "https://shop1.1688.com"},
                },
            )
        self.assertEqual(client.completed["status"], "failed")
        self.assertIn("A1688", client.completed["error_code"])
