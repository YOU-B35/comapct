import unittest
from unittest.mock import MagicMock, patch

from agent.handlers import handle_temu_competitor_discover
from agent.temu_tasks import open_login_window


class TemuTaskThreadingTests(unittest.TestCase):
    def test_open_login_window_opens_runtime_without_background_thread(self):
        fake_page = MagicMock()
        fake_runtime = MagicMock()
        fake_runtime.context = object()

        with patch("agent.temu_tasks.get_or_create_temu_runtime", return_value=fake_runtime, create=True) as get_runtime, \
                patch("agent.temu_tasks.get_or_open_seller_page", return_value=fake_page, create=True) as get_page, \
                patch("agent.temu_tasks.close_temu_runtime", create=True), \
                patch("agent.temu_tasks.close_tenant_profile_browsers", create=True), \
                patch("agent.temu_tasks.is_profile_locked", return_value=False, create=True), \
                patch("agent.temu_tasks.TEMU_SELLER_HOME", "https://agentseller.temu.com", create=True):
            result = open_login_window(tenant_id=5)

        self.assertTrue(result["opened"])
        self.assertFalse(result["already_open"])
        get_runtime.assert_called_once_with(5, headless=False)
        get_page.assert_called_once_with(fake_runtime.context)
        fake_page.bring_to_front.assert_called_once()

    def test_handle_temu_competitor_discover_runs_inline(self):
        client = MagicMock()
        task = {
            "task_id": "agt-test",
            "payload": {
                "tenant_id": 5,
                "keyword": "fishing tackle",
                "region": "za",
                "limit": 5,
            },
        }
        result = {"keyword": "fishing tackle", "region": "za", "candidates": []}

        with patch("agent.handlers.discover_competitors", return_value=result) as discover, \
                patch("agent.handlers.ThreadPoolExecutor", side_effect=AssertionError("should not use executor")):
            handle_temu_competitor_discover(client, task)

        discover.assert_called_once_with(5, "fishing tackle", "za", 5)
        client.complete_task_with_retry.assert_called_once_with(
            "agt-test",
            status="success",
            result=result,
        )


if __name__ == "__main__":
    unittest.main()
