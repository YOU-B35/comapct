import tempfile
import unittest
from pathlib import Path

from app.config import resolve_aliexpress_profile_dir, resolve_profile_dir
from app.session_scope import (
    build_session_key,
    normalize_session_key,
    resolve_platform_profile_dir,
)


class SharedSessionScopeTests(unittest.TestCase):
    def test_build_session_key_from_account(self):
        self.assertEqual(build_session_key("138-0013-8000", ""), "138_0013_8000")
        self.assertEqual(build_session_key("seller@example.com", "pa-1"), "seller_example_com")

    def test_build_session_key_fallback(self):
        self.assertEqual(build_session_key("", "abc123"), "pa_abc123")
        self.assertEqual(normalize_session_key(""), "default")

    def test_platform_profile_nested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = resolve_platform_profile_dir("temu", 5, "18061740604", root=root)
            self.assertEqual(path, root / "tenant-5" / "account-18061740604")

    def test_platform_profile_legacy_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "tenant-5"
            legacy.mkdir(parents=True)
            path = resolve_platform_profile_dir("aliexpress", 5, "default", root=root)
            self.assertEqual(path, legacy)

    def test_ae_and_temu_resolvers_accept_session_key(self):
        # smoke: callables accept session_key without error (path under configured roots)
        temu = resolve_profile_dir(5, "acct_a")
        ae = resolve_aliexpress_profile_dir(5, "acct_b")
        self.assertIn("account-acct_a", str(temu).replace("\\", "/"))
        self.assertIn("account-acct_b", str(ae).replace("\\", "/"))
        self.assertNotEqual(temu, ae)


if __name__ == "__main__":
    unittest.main()
