import json
import unittest
from unittest.mock import MagicMock, patch

from app.crawler.temu_api import TemuApiClient, TemuMappingError, _retryable_status


class TemuApiRetryTests(unittest.TestCase):
    def _client(self) -> TemuApiClient:
        client = object.__new__(TemuApiClient)
        client.mall_id = "mall-1"
        client.page = MagicMock()
        return client

    def test_retries_transient_http_failure_then_returns_data(self):
        client = self._client()
        client.page.evaluate.side_effect = [
            {"status": 503, "text": "temporarily unavailable"},
            {"status": 200, "text": json.dumps({"success": True, "result": {}})},
        ]

        with patch("app.crawler.temu_api.human_pause"), \
                patch("app.crawler.temu_api.dismiss_temu_ui_blockers"), \
                patch("app.crawler.temu_api.time.sleep") as sleep:
            result = client._post("https://example.test/sales", {})

        self.assertEqual(result["success"], True)
        self.assertEqual(client.page.evaluate.call_count, 2)
        sleep.assert_called_once_with(1.0)

    def test_timeout_response_recovers_page_before_retry(self):
        client = self._client()
        client.page.evaluate.side_effect = [
            {"error": "The operation was aborted", "timedOut": True},
            {"status": 200, "text": json.dumps({"success": True, "result": {}})},
        ]

        with patch("app.crawler.temu_api.human_pause"), \
                patch("app.crawler.temu_api.dismiss_temu_ui_blockers") as dismiss, \
                patch("app.crawler.temu_api.ensure_fully_managed_sales_page") as ensure_page, \
                patch("app.crawler.temu_api.time.sleep"):
            client._post("https://example.test/sales", {})

        self.assertEqual(ensure_page.call_count, 1)
        self.assertTrue(any(call.kwargs.get("rounds") == 3 for call in dismiss.call_args_list))

    def test_business_mapping_error_is_not_retried(self):
        client = self._client()
        client.page.evaluate.return_value = {
            "status": 200,
            "text": json.dumps({"success": False, "errorCode": "2000000"}),
        }

        with patch("app.crawler.temu_api.human_pause"), \
                patch("app.crawler.temu_api.dismiss_temu_ui_blockers"), \
                patch("app.crawler.temu_api.time.sleep") as sleep:
            with self.assertRaises(TemuMappingError):
                client._post("https://example.test/sales", {})

        self.assertEqual(client.page.evaluate.call_count, 1)
        sleep.assert_not_called()

    def test_retryable_statuses_are_limited_to_transient_failures(self):
        self.assertTrue(_retryable_status(429))
        self.assertTrue(_retryable_status(503))
        self.assertFalse(_retryable_status(401))
        self.assertFalse(_retryable_status(422))


if __name__ == "__main__":
    unittest.main()
