from __future__ import annotations

import unittest
from unittest.mock import patch

from agent.agent_tools import TOOL_SCHEMAS, dispatch_tool


class AgentToolsTest(unittest.TestCase):
    def test_schemas_have_required_fields(self) -> None:
        self.assertGreaterEqual(len(TOOL_SCHEMAS), 8)
        for schema in TOOL_SCHEMAS:
            fn = schema["function"]
            self.assertIn("name", fn)
            self.assertIn("description", fn)
            self.assertIn("parameters", fn)
            self.assertTrue(fn["description"].strip())

    def test_unknown_tool_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            dispatch_tool("no_such_tool", {})

    def test_dispatch_doctor(self) -> None:
        with patch(
            "agent.agent_tools.cli_tools.ziniao_doctor",
            return_value={"ok": True, "data": "ok", "summary": "ok", "error": ""},
        ) as mock_doctor:
            result = dispatch_tool("ziniao_doctor", {})
        mock_doctor.assert_called_once()
        self.assertTrue(result["ok"])

    def test_dispatch_store_open_passes_args(self) -> None:
        with patch(
            "agent.agent_tools.cli_tools.ziniao_store_open",
            return_value={"ok": True, "data": None, "summary": "opened", "error": ""},
        ) as mock_open:
            dispatch_tool("ziniao_store_open", {"store_id": "s1", "url": "https://sellercentral.amazon.com"})
        mock_open.assert_called_once_with("s1", "https://sellercentral.amazon.com")

    def test_dispatch_csv_read(self) -> None:
        with patch(
            "agent.agent_tools.cli_tools.read_csv_file",
            return_value={"ok": True, "data": [], "summary": "CSV 0 行", "error": ""},
        ) as mock_csv:
            dispatch_tool("csv_read", {"path": "report.csv", "max_rows": 10})
        mock_csv.assert_called_once_with("report.csv", 10)


if __name__ == "__main__":
    unittest.main()
