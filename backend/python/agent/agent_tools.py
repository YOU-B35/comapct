"""Function-calling tool schemas and dispatch for the agent kernel."""
from __future__ import annotations

from typing import Any

from app.ziniao import cli_tools


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "ziniao_doctor",
            "description": "检查本机紫鸟 CLI 与客户端环境是否可用。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ziniao_store_list",
            "description": "列出紫鸟中已绑定且可用的店铺。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ziniao_store_open",
            "description": "打开指定紫鸟店铺浏览器，可带初始 URL。",
            "parameters": {
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "紫鸟店铺 ID 或浏览器 ID"},
                    "url": {"type": "string", "description": "初始 URL，可省略"},
                },
                "required": ["store_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ziniao_page_visit",
            "description": "让指定店铺浏览器导航到目标 URL。",
            "parameters": {
                "type": "object",
                "properties": {
                    "store_id": {"type": "string"},
                    "url": {"type": "string"},
                    "wait_until": {"type": "string", "enum": ["domcontentloaded", "load", "networkidle"]},
                },
                "required": ["store_id", "url"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ziniao_page_content",
            "description": "读取当前页面结构化内容，表格/列表优先。",
            "parameters": {
                "type": "object",
                "properties": {
                    "store_id": {"type": "string"},
                    "content_format": {"type": "string", "enum": ["structured", "text", "html"]},
                },
                "required": ["store_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ziniao_page_exec",
            "description": "在店铺页面执行 JS，用于滚动、点击导出或读取下载。",
            "parameters": {
                "type": "object",
                "properties": {"store_id": {"type": "string"}, "js": {"type": "string"}},
                "required": ["store_id", "js"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ziniao_automation_run",
            "description": "执行多步浏览器编排，steps 为 JSON 步骤数组字符串。",
            "parameters": {
                "type": "object",
                "properties": {"steps": {"type": "string"}},
                "required": ["steps"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ziniao_page_screenshot",
            "description": "对当前店铺页面截图保存到指定路径。",
            "parameters": {
                "type": "object",
                "properties": {"store_id": {"type": "string"}, "path": {"type": "string"}},
                "required": ["store_id", "path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "csv_read",
            "description": "读取官方导出的 CSV 文件，返回裁剪后的结构化行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_rows": {"type": "integer", "minimum": 1, "maximum": 1000},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
]


def dispatch_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    args = args if isinstance(args, dict) else {}
    if name == "ziniao_doctor":
        return cli_tools.ziniao_doctor()
    if name == "ziniao_store_list":
        return cli_tools.ziniao_store_list()
    if name == "ziniao_store_open":
        return cli_tools.ziniao_store_open(str(args.get("store_id") or ""), str(args.get("url") or ""))
    if name == "ziniao_page_visit":
        return cli_tools.ziniao_page_visit(
            str(args.get("store_id") or ""),
            str(args.get("url") or ""),
            str(args.get("wait_until") or "domcontentloaded"),
        )
    if name == "ziniao_page_content":
        return cli_tools.ziniao_page_content(
            str(args.get("store_id") or ""),
            str(args.get("content_format") or "structured"),
        )
    if name == "ziniao_page_exec":
        return cli_tools.ziniao_page_exec(str(args.get("store_id") or ""), str(args.get("js") or ""))
    if name == "ziniao_automation_run":
        return cli_tools.ziniao_automation_run(str(args.get("steps") or ""))
    if name == "ziniao_page_screenshot":
        return cli_tools.ziniao_page_screenshot(str(args.get("store_id") or ""), str(args.get("path") or ""))
    if name == "csv_read":
        return cli_tools.read_csv_file(str(args.get("path") or ""), int(args.get("max_rows") or 200))
    raise KeyError(f"未知工具: {name}")
