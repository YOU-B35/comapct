import unittest
from unittest.mock import MagicMock, patch

from agent.handlers import handle_temu_competitor_discover
from agent.temu_tasks import open_login_window


class TemuTaskThreadingTests(unittest.TestCase):
    def test_open_login_window_opens_runtime_without_background_thread(self):
        fake_page = MagicMock()
        fake_page.url = "https://agentseller.temu.com/"
        fake_runtime = MagicMock()
        fake_runtime.context = object()

        with patch("agent.temu_tasks.browser_runtime.peek_browser_runtime", return_value=None), \
                patch("agent.temu_tasks.get_or_create_temu_runtime", return_value=fake_runtime) as get_runtime, \
                patch("agent.temu_tasks.ensure_seller_login_page", return_value=fake_page) as ensure_page, \
                patch("agent.temu_tasks.close_temu_runtime"), \
                patch("agent.temu_tasks.close_tenant_profile_browsers"), \
                patch("agent.temu_tasks.sanitize_profile_startup_for_temu", create=True), \
                patch("app.browser.profile_startup.sanitize_profile_startup_for_temu"), \
                patch("agent.temu_tasks.TEMU_SELLER_HOME", "https://agentseller.temu.com/"):
            result = open_login_window(tenant_id=5)

        self.assertTrue(result["opened"])
        self.assertFalse(result["already_open"])
        self.assertFalse(result["reused"])
        get_runtime.assert_called_once_with(
            5,
            headless=False,
            session_key="default",
            skip_profile_pull=True,
            force_kill_browsers=True,
        )
        ensure_page.assert_called_once_with(fake_runtime.context, force_navigate=True)

    def test_open_login_window_reuses_live_runtime(self):
        fake_page = MagicMock()
        fake_page.url = "https://agentseller.temu.com/"
        peeked = MagicMock()
        peeked.context = object()

        with patch("agent.temu_tasks.browser_runtime.peek_browser_runtime", return_value=peeked), \
                patch("agent.temu_tasks.is_runtime_context_usable", return_value=True), \
                patch("agent.temu_tasks.ensure_seller_login_page", return_value=fake_page) as ensure_page, \
                patch("agent.temu_tasks.get_or_create_temu_runtime") as get_runtime, \
                patch("agent.temu_tasks.is_profile_locked", return_value=False):
            result = open_login_window(tenant_id=5, session_key="acct1")

        self.assertTrue(result["opened"])
        self.assertTrue(result["reused"])
        ensure_page.assert_called_once_with(peeked.context, force_navigate=True)
        get_runtime.assert_not_called()

    def test_handle_temu_competitor_discover_runs_via_discover_competitors(self):
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

        with patch("agent.handlers.discover_competitors", return_value=result) as discover:
            handle_temu_competitor_discover(client, task)

        discover.assert_called_once_with(5, "fishing tackle", "za", 5)
        client.complete_task_with_retry.assert_called_once_with(
            "agt-test",
            status="success",
            result=result,
        )

    def test_discover_competitors_runs_in_worker_thread(self):
        from agent import temu_tasks

        seen: dict[str, int] = {}

        def fake_discover(**kwargs):
            import threading

            seen["thread"] = threading.get_ident()
            return {"candidates": [], "tenant_id": kwargs["tenant_id"]}

        with patch.object(temu_tasks, "close_temu_runtime") as close_rt, \
                patch("app.crawler.competitor_discovery.discover_competitor_candidates", side_effect=fake_discover):
            out = temu_tasks.discover_competitors(5, "fishing", "za", 3)

        self.assertEqual(out["tenant_id"], 5)
        close_rt.assert_called_once_with(5)
        self.assertNotEqual(seen.get("thread"), __import__("threading").get_ident())


if __name__ == "__main__":
    unittest.main()
