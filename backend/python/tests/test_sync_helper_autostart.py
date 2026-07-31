"""RC-AUTO: Sync Helper autostart scripts exist and wire correctly."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"


class SyncHelperAutostartTests(unittest.TestCase):
    def test_install_script_registers_logon_task(self):
        text = (SCRIPTS / "install-sync-helper-autostart.ps1").read_text(encoding="utf-8")
        self.assertIn("Register-ScheduledTask", text)
        self.assertIn("AtLogOn", text)
        self.assertIn("CrossHub-Sync-Helper", text)
        self.assertIn("start-sync-helper-autostart.ps1", text)

    def test_launcher_prefers_exe_and_checks_health(self):
        text = (SCRIPTS / "start-sync-helper-autostart.ps1").read_text(encoding="utf-8")
        self.assertIn("CrossHub-Sync-Helper.exe", text)
        self.assertIn("/health", text)
        self.assertIn("HealthPort = 18765", text)
        self.assertIn("run-agent.ps1", text)
        self.assertIn("autostart-", text)

    def test_uninstall_script_unregisters_task(self):
        text = (SCRIPTS / "uninstall-sync-helper-autostart.ps1").read_text(encoding="utf-8")
        self.assertIn("Unregister-ScheduledTask", text)
        self.assertIn("CrossHub-Sync-Helper", text)

    def test_checklist_doc_exists(self):
        path = ROOT / "docs" / "superpowers" / "specs" / "attachments" / "2026-07-29-rc-auto-checklist.md"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("install-sync-helper-autostart.ps1", text)
        self.assertIn("18765/health", text)


if __name__ == "__main__":
    unittest.main()
