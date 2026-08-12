import unittest

from app.browser.session_state import build_session_payload, session_ready
from app.browser.profile_lock import (
    SESSION_CACHE_BUSY_MAX_AGE_SECONDS,
    SESSION_CACHE_READY_MAX_AGE_SECONDS,
)


class SessionStateTests(unittest.TestCase):
    def test_session_ready_when_mall_id_present(self):
        self.assertTrue(session_ready({"mall_id": "mall-1", "requires_auth": False}))

    def test_session_ready_false_on_auth_without_malls(self):
        self.assertFalse(session_ready({"requires_auth": True, "logged_in": False, "mall_count": 0}))

    def test_build_payload_marks_profile_busy(self):
        payload = build_session_payload(
            5,
            {"requires_auth": True, "logged_in": False, "mall_count": 0},
            profile_busy=True,
        )
        self.assertTrue(payload["profile_busy"])
        self.assertFalse(payload["ready"])

    def test_ready_cache_fallback_age_is_days(self):
        # Wall-clock fallback when Cookie DB unreadable; primary trust is cookie expiry.
        self.assertGreaterEqual(SESSION_CACHE_READY_MAX_AGE_SECONDS, 7 * 24 * 3600)
        self.assertLessEqual(SESSION_CACHE_BUSY_MAX_AGE_SECONDS, SESSION_CACHE_READY_MAX_AGE_SECONDS)


if __name__ == "__main__":
    unittest.main()
