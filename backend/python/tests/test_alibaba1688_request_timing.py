import unittest
from unittest.mock import patch

from agent.alibaba1688_order_tasks import _mtop
from app.observability.task_timing import finish_task_timing, start_task_timing


class _Context:
    def cookies(self):
        return [{"name": "_m_h5_tk", "value": "token123_suffix"}]


class _Page:
    context = _Context()

    def evaluate(self, _script, _payload):
        return {"ret": ["SUCCESS::ok"], "data": {}}


class Alibaba1688RequestTimingTests(unittest.TestCase):
    def test_mtop_request_is_included_in_task_timing(self):
        timing, token = start_task_timing("1688_orders_sync", "task-1688")

        result = _mtop(_Page(), "mtop.1688.trading.dataline.service", {"page": 1})

        payload = finish_task_timing(timing, token, outcome="handled")
        self.assertTrue(result["ret"][0].startswith("SUCCESS"))
        self.assertIn("a1688_mtop.request", payload["stages_ms"])

    def test_mtop_retries_browser_wrapped_transient_response_with_fresh_signature(self):
        payloads = []

        class FlakyPage(_Page):
            def evaluate(self, _script, payload):
                payloads.append(payload)
                if len(payloads) == 1:
                    return {"ret": ["FAIL::TimeoutError"]}
                return {"ret": ["SUCCESS::ok"], "data": {}}

        with patch("app.rate_limit.time.sleep"), \
                patch("agent.alibaba1688_order_tasks.time.time", side_effect=[1000.0, 1001.0]):
            result = _mtop(FlakyPage(), "mtop.1688.trading.dataline.service", {"page": 1})

        self.assertTrue(result["ret"][0].startswith("SUCCESS"))
        self.assertEqual(len(payloads), 2)
        self.assertIn("t=1000000", payloads[0]["url"])
        self.assertIn("t=1001000", payloads[1]["url"])


if __name__ == "__main__":
    unittest.main()
