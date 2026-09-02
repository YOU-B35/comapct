import unittest
from unittest.mock import patch

from agent import pdd_tasks


class PddReplayTransportRetryTests(unittest.TestCase):
    def test_retries_transient_network_failure_with_short_delay(self):
        calls = []

        def replay(*_args, **_kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("request timeout")
            return {"result": {"pageItems": []}}

        with patch("agent.pdd_tasks._replay_page", side_effect=replay), \
                patch("agent.pdd_tasks.time.sleep") as sleep:
            result = pdd_tasks._replay_with_retry(
                object(),
                method="GET",
                url="https://mms.pinduoduo.com/list",
                headers={},
                post_data=None,
                page_no=1,
                page_size=50,
            )

        self.assertEqual(result["result"]["pageItems"], [])
        self.assertEqual(len(calls), 2)
        sleep.assert_called_once_with(1.0)

    def test_does_not_retry_non_transport_error(self):
        with patch("agent.pdd_tasks._replay_page", side_effect=ValueError("bad payload")) as replay, \
                patch("agent.pdd_tasks.time.sleep") as sleep:
            with self.assertRaisesRegex(ValueError, "bad payload"):
                pdd_tasks._replay_with_retry(
                    object(),
                    method="GET",
                    url="https://mms.pinduoduo.com/list",
                    headers={},
                    post_data=None,
                    page_no=1,
                    page_size=50,
                )

        replay.assert_called_once()
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
