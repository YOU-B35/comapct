from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from app.ziniao import cli_tools


class CompletedProc:
    def __init__(self, rc, out="", err=""):
        self.returncode = rc
        self.stdout = out
        self.stderr = err


class ZiniaoCliToolsTest(unittest.TestCase):
    def test_missing_cli_returns_not_ok(self) -> None:
        with patch("app.ziniao.cli_tools.shutil.which", return_value=None):
            result = cli_tools.ziniao_doctor()
        self.assertFalse(result["ok"])
        self.assertIn("未检测到", result["summary"])

    def test_doctor_runs_cli_and_reports_ok(self) -> None:
        with patch("app.ziniao.cli_tools.shutil.which", return_value="C:\\bin\\ziniao-cli.exe"):
            with patch(
                "app.ziniao.cli_tools.subprocess.run",
                return_value=CompletedProc(0, "ziniao ok"),
            ) as run:
                result = cli_tools.ziniao_doctor()
        self.assertTrue(result["ok"])
        self.assertEqual(run.call_args[0][0], ["C:\\bin\\ziniao-cli.exe", "doctor"])
        self.assertIn("ziniao ok", result["summary"])

    def test_store_open_passes_store_id_and_url(self) -> None:
        with patch("app.ziniao.cli_tools.shutil.which", return_value="ziniao-cli"):
            with patch(
                "app.ziniao.cli_tools.subprocess.run",
                return_value=CompletedProc(0, ""),
            ) as run:
                result = cli_tools.ziniao_store_open("s1", "https://sellercentral.amazon.com")
        self.assertTrue(result["ok"])
        args = run.call_args[0][0]
        self.assertIn("s1", args)
        self.assertIn("https://sellercentral.amazon.com", args)

    def test_page_content_uses_structured_format(self) -> None:
        with patch("app.ziniao.cli_tools.shutil.which", return_value="ziniao-cli"):
            with patch(
                "app.ziniao.cli_tools.subprocess.run",
                return_value=CompletedProc(0, '{"rows": []}'),
            ) as run:
                result = cli_tools.ziniao_page_content("s1")
        self.assertTrue(result["ok"])
        args = run.call_args[0][0]
        self.assertIn("--content-format", args)
        self.assertIn("structured", args)

    def test_read_csv_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "report.csv")
            with open(path, "w", newline="", encoding="utf-8") as fh:
                fh.write("asin,orders_30d\nB0TEST,5\n")
            result = cli_tools.read_csv_file(path)
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"][0]["asin"], "B0TEST")
        self.assertEqual(result["data"][0]["orders_30d"], "5")

    def test_read_csv_missing_file(self) -> None:
        result = cli_tools.read_csv_file("C:/no/such/file.csv")
        self.assertFalse(result["ok"])
        self.assertIn("不存在", result["summary"])


if __name__ == "__main__":
    unittest.main()
