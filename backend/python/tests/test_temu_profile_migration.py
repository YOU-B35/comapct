"""Tests for legacy Temu profile migration."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.temu.profile_migration import maybe_migrate_legacy_temu_profile


class TemuProfileMigrationTest(unittest.TestCase):
    def test_migrates_legacy_ready_profile_to_account_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "tenant-5"
            legacy.mkdir(parents=True)
            cookies = legacy / "Default" / "Network"
            cookies.mkdir(parents=True)
            (cookies / "Cookies").write_bytes(b"x" * 12000)
            (legacy / ".crosshub-session.json").write_text(
                json.dumps({"ready": True, "mall_id": "634418211126671"}),
                encoding="utf-8",
            )

            import os

            os.environ["TEMU_PROFILE_ROOT"] = str(root)
            migrated = maybe_migrate_legacy_temu_profile(5, "18061740604")
            self.assertTrue(migrated)

            nested = root / "tenant-5" / "account-18061740604"
            self.assertTrue((nested / "Default" / "Network" / "Cookies").is_file())
            cache = json.loads((nested / ".crosshub-session.json").read_text(encoding="utf-8"))
            self.assertTrue(cache.get("ready"))
            self.assertEqual(cache.get("session_key"), "18061740604")

    def test_skips_when_account_profile_already_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "tenant-5"
            legacy.mkdir(parents=True)
            cookies = legacy / "Default" / "Network"
            cookies.mkdir(parents=True)
            (cookies / "Cookies").write_bytes(b"x" * 12000)
            (legacy / ".crosshub-session.json").write_text(
                json.dumps({"ready": True}),
                encoding="utf-8",
            )

            nested = root / "tenant-5" / "account-18061740604"
            nested.mkdir(parents=True)
            nested_cookies = nested / "Default" / "Network"
            nested_cookies.mkdir(parents=True)
            (nested_cookies / "Cookies").write_bytes(b"x" * 12000)
            (nested / ".crosshub-session.json").write_text(
                json.dumps({"ready": True, "session_key": "18061740604"}),
                encoding="utf-8",
            )

            import os

            os.environ["TEMU_PROFILE_ROOT"] = str(root)
            self.assertFalse(maybe_migrate_legacy_temu_profile(5, "18061740604"))


if __name__ == "__main__":
    unittest.main()
