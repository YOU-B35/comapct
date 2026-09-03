from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sync_helper_app


class SyncHelperZiniaoStartupTests(unittest.TestCase):
    def test_cli_install_without_ready_bridge_does_not_start_webdriver(self) -> None:
        with patch(
            "app.ziniao.cli_tools.prepare_bundled_cli",
            return_value={"ok": True, "summary": "紫鸟 CLI 已就绪"},
        ), patch(
            "app.ziniao.cli_tools.ziniao_doctor",
            return_value={"ok": False, "summary": "ZClaw Bridge 未启动"},
        ), patch.object(sync_helper_app, "ZINIAO_EXE"), patch(
            "sync_helper_app.subprocess.Popen"
        ) as popen, patch.dict(os.environ, {}, clear=True):
            sync_helper_app.maybe_start_ziniao()

        popen.assert_not_called()

    def test_ready_cli_keeps_normal_mode_browser_untouched(self) -> None:
        with patch(
            "app.ziniao.cli_tools.prepare_bundled_cli",
            return_value={"ok": True, "summary": "紫鸟 CLI 已就绪"},
        ), patch(
            "app.ziniao.cli_tools.ziniao_doctor",
            return_value={"ok": True, "summary": "紫鸟 CLI 与 ZClaw Bridge 已就绪"},
        ), patch(
            "sync_helper_app.subprocess.Popen"
        ) as popen, patch.dict(os.environ, {}, clear=True):
            sync_helper_app.maybe_start_ziniao()

        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
