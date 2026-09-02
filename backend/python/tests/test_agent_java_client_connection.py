from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from agent.java_client import AgentApiClient


class AgentJavaClientConnectionTest(unittest.TestCase):
    def test_control_requests_reuse_one_http_client(self) -> None:
        response = MagicMock()
        response.json.side_effect = [{"data": []}, {"ok": True}]
        http = MagicMock()
        http.get.return_value = response
        http.post.return_value = response

        with patch("agent.java_client.httpx.Client", return_value=http) as client_factory:
            client = AgentApiClient(token="test-token", base_url="https://example.test")
            self.assertEqual(client.poll_tasks(), [])
            client.heartbeat(ziniao_online=True)
            client.close()

        self.assertEqual(client_factory.call_count, 1)
        http.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
