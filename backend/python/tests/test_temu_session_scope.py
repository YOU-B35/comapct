import unittest

from app.temu.session_aggregate import aggregate_tenant_sessions
from app.temu.session_scope import build_temu_session_key, normalize_session_key


class TemuSessionScopeTests(unittest.TestCase):
    def test_build_session_key_from_account(self):
        self.assertEqual(build_temu_session_key("138-0013-8000", ""), "138_0013_8000")
        self.assertEqual(
            build_temu_session_key("seller@example.com", "pa-1"),
            "seller_example_com",
        )

    def test_build_session_key_fallback_platform_account(self):
        self.assertEqual(build_temu_session_key("", "abc123"), "pa_abc123")

    def test_aggregate_all_ready(self):
        payload = aggregate_tenant_sessions(
            5,
            [
                {"session_key": "a", "ready": True, "logged_in": True, "mall_count": 2},
                {"session_key": "b", "ready": True, "logged_in": True, "mall_count": 1},
            ],
        )
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["ready_count"], 2)
        self.assertEqual(payload["session_count"], 2)

    def test_normalize_session_key(self):
        self.assertEqual(normalize_session_key(None), "default")
        self.assertEqual(normalize_session_key(""), "default")


if __name__ == "__main__":
    unittest.main()
