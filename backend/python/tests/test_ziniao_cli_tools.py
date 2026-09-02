from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

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

    @unittest.skipUnless(os.name == "nt", "Windows-only npm shim")
    def test_npm_shim_js_entry_extracts_run_js(self) -> None:
        shim = (
            '@ECHO off\r\n'
            'SET dp0=%~dp0\r\n'
            'endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%"  "%dp0%\\..\\@ziniao-open\\cli\\scripts\\run.js" %*\r\n'
        )
        with tempfile.TemporaryDirectory() as td:
            cmd_path = os.path.join(td, "ziniao-cli.cmd")
            with open(cmd_path, "w", encoding="utf-8") as fh:
                fh.write(shim)
            entry = cli_tools._npm_shim_js_entry(cmd_path)
        self.assertIsNotNone(entry)
        self.assertTrue(str(entry).endswith(os.path.join("@ziniao-open", "cli", "scripts", "run.js")))

    @unittest.skipUnless(os.name == "nt", "Windows-only shim launch")
    def test_resolve_launch_cmd_uses_node(self) -> None:
        with patch(
            "app.ziniao.cli_tools._npm_shim_js_entry",
            return_value=Path("C:/pkg/scripts/run.js"),
        ):
            launch = cli_tools._resolve_cli_launch("C:/bin/ziniao-cli.cmd")
        self.assertEqual(launch, ["node", str(Path("C:/pkg/scripts/run.js"))])

    @unittest.skipUnless(os.name == "nt", "Windows-only js launch")
    def test_resolve_launch_js_uses_node(self) -> None:
        launch = cli_tools._resolve_cli_launch("C:/pkg/scripts/run.js")
        self.assertEqual(launch, ["node", "C:/pkg/scripts/run.js"])

    def test_store_open_uses_id_flag(self) -> None:
        with patch("app.ziniao.cli_tools.shutil.which", return_value="ziniao-cli"):
            with patch(
                "app.ziniao.cli_tools.subprocess.run",
                return_value=CompletedProc(0, ""),
            ) as run:
                cli_tools.ziniao_store_open("s1", "https://sellercentral.amazon.com")
        args = run.call_args[0][0]
        self.assertIn("--id", args)
        self.assertIn("s1", args)
        self.assertNotIn("--store-id", args)

    def test_page_exec_uses_script_flag(self) -> None:
        with patch("app.ziniao.cli_tools.shutil.which", return_value="ziniao-cli"):
            with patch(
                "app.ziniao.cli_tools.subprocess.run",
                return_value=CompletedProc(0, ""),
            ) as run:
                cli_tools.ziniao_page_exec("s1", "return 1;")
        args = run.call_args[0][0]
        self.assertIn("--script", args)
        self.assertIn("return 1;", args)
        self.assertNotIn("--js", args)

    def test_store_list_parses_json_items(self) -> None:
        body = json.dumps(
            {
                "ok": True,
                "data": {
                    "items": [{"storeId": "a1", "storeName": "Store A", "platformName": "亚马逊-美国"}],
                    "total": 1,
                },
            },
            ensure_ascii=False,
        )
        with patch("app.ziniao.cli_tools.shutil.which", return_value="ziniao-cli"):
            with patch(
                "app.ziniao.cli_tools.subprocess.run",
                return_value=CompletedProc(0, body),
            ) as run:
                result = cli_tools.ziniao_store_list()
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"][0]["storeId"], "a1")
        self.assertIn("1", result["summary"])

    def test_store_list_parses_flat_json_items(self) -> None:
        body = json.dumps(
            {"items": [{"storeId": "b2", "storeName": "Store B"}], "total": 1},
            ensure_ascii=False,
        )
        with patch("app.ziniao.cli_tools.shutil.which", return_value="ziniao-cli"):
            with patch(
                "app.ziniao.cli_tools.subprocess.run",
                return_value=CompletedProc(0, body),
            ) as run:
                result = cli_tools.ziniao_store_list()
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"][0]["storeId"], "b2")

    def test_run_cli_decodes_utf8_output(self) -> None:
        with patch("app.ziniao.cli_tools.shutil.which", return_value="ziniao-cli"):
            with patch(
                "app.ziniao.cli_tools.subprocess.run",
                return_value=CompletedProc(0, "紫鸟 ok"),
            ) as run:
                result = cli_tools.ziniao_doctor()
        self.assertTrue(result["ok"])
        self.assertIn("紫鸟", result["summary"])
        kwargs = run.call_args[1]
        self.assertEqual(kwargs.get("encoding"), "utf-8")
        self.assertEqual(kwargs.get("errors"), "replace")


if __name__ == "__main__":
    unittest.main()
