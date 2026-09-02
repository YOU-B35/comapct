import unittest
from unittest.mock import MagicMock, patch

from app.crawler.aliexpress_api import AliExpressApiClient


class _Response:
    def __init__(self, status: int, body=None):
        self.status = status
        self.ok = 200 <= status < 300
        self._body = {} if body is None else body

    def json(self):
        return self._body

    def text(self):
        return "response body"


class AliExpressApiRetryTests(unittest.TestCase):
    def _client(self):
        client = object.__new__(AliExpressApiClient)
        client.page = MagicMock()
        return client

    def test_form_request_retries_transient_status(self):
        client = self._client()
        client.page.request.post.side_effect = [_Response(503), _Response(200, {"success": True})]

        with patch("app.crawler.aliexpress_api.human_pause"), \
                patch("app.crawler.aliexpress_api.time.sleep") as sleep:
            result = client._post_form("https://example.test/api", {"page": 1}, referer="https://example.test")

        self.assertTrue(result["success"])
        self.assertEqual(client.page.request.post.call_count, 2)
        sleep.assert_called_once_with(1.0)

    def test_form_request_does_not_retry_non_transient_status(self):
        client = self._client()
        client.page.request.post.return_value = _Response(401)

        with patch("app.crawler.aliexpress_api.human_pause"), \
                patch("app.crawler.aliexpress_api.time.sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "HTTP 401"):
                client._post_form("https://example.test/api", {}, referer="https://example.test")

        self.assertEqual(client.page.request.post.call_count, 1)
        sleep.assert_not_called()

    def test_violations_api_remains_a_client_method(self):
        self.assertTrue(callable(getattr(AliExpressApiClient, "fetch_violations", None)))


if __name__ == "__main__":
    unittest.main()
