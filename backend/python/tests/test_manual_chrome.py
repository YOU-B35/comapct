import unittest
from unittest.mock import patch

from app.browser import manual_chrome


class ManualChromeTests(unittest.TestCase):
    def test_open_manual_frontend_chrome_releases_runtime_and_spawns(self):
        with patch.object(manual_chrome, "close_temu_runtime") as close_runtime, \
                patch.object(manual_chrome, "close_tenant_profile_browsers", return_value=1) as close_browsers, \
                patch.object(manual_chrome, "find_chrome_executable", return_value="chrome.exe"), \
                patch.object(manual_chrome, "resolve_profile_dir", return_value=manual_chrome.Path("tmp-profile")), \
                patch.object(manual_chrome.subprocess, "Popen") as popen, \
                patch.object(manual_chrome.Path, "mkdir"):
            result = manual_chrome.open_manual_frontend_chrome(5, "https://www.temu.com/")

        self.assertTrue(result["opened"])
        self.assertEqual(result["engine"], "manual_chrome")
        close_runtime.assert_called_once_with(5)
        close_browsers.assert_called_once_with(5)
        popen.assert_called_once()
        args = popen.call_args[0][0]
        self.assertIn("--user-data-dir=tmp-profile", args)
        self.assertIn("https://www.temu.com/", args)

    def test_frontend_login_required_error_code(self):
        err = manual_chrome.frontend_login_required_error({"url": "https://www.temu.com/"})
        self.assertTrue(str(err).startswith("COMPETITOR_LOGIN_REQUIRED:"))


if __name__ == "__main__":
    unittest.main()
