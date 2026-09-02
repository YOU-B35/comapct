import unittest
from unittest.mock import patch

from app.crawler import temu_crawler


class TemuProfilePrepareTests(unittest.TestCase):
    def test_ready_profile_does_not_add_fixed_wait_after_noop_reclaim(self):
        cached = {"ready": True, "logged_in": True}

        with patch("agent.handlers._temu_panel_logging_in", return_value=False), \
                patch("app.browser.context.close_temu_runtime"), \
                patch.object(temu_crawler, "read_ready_session_cache", return_value=cached), \
                patch.object(temu_crawler, "session_ready", return_value=True), \
                patch.object(temu_crawler, "close_tenant_profile_browsers", return_value=0) as reclaim, \
                patch.object(temu_crawler, "clear_profile_lock") as clear_lock, \
                patch.object(temu_crawler.time, "sleep") as sleep:
            temu_crawler.ensure_profile_available(5, session_key="store-a")

        reclaim.assert_called_once_with(5, session_key="store-a")
        clear_lock.assert_called_once_with(5, "store-a")
        sleep.assert_not_called()

    def test_unlocked_profile_does_not_add_fixed_wait_after_noop_reclaim(self):
        with patch("agent.handlers._temu_panel_logging_in", return_value=False), \
                patch("app.browser.context.close_temu_runtime"), \
                patch.object(temu_crawler, "read_ready_session_cache", return_value=None), \
                patch.object(temu_crawler, "is_profile_locked", return_value=False), \
                patch.object(temu_crawler, "close_tenant_profile_browsers", return_value=0) as reclaim, \
                patch.object(temu_crawler.time, "sleep") as sleep:
            temu_crawler.ensure_profile_available(5, session_key="store-a")

        reclaim.assert_called_once_with(5, session_key="store-a")
        sleep.assert_not_called()

