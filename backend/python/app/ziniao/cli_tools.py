"""Thin wrappers around the Ziniao official CLI for the LLM agent tool layer."""
from __future__ import annotations

import csv
import os
import shutil
import subprocess
from typing import Any


def _tool_timeout(default: float) -> float:
    try:
        return float(os.environ.get("AMAZON_CHAT_TOOL_TIMEOUT_SECONDS", str(default)))
    except ValueError:
        return default


def _trim(text: str, limit: int = 2000) -> str:
    return text[:limit] + ("..." if len(text) > limit else "")


def _run_cli(args: list[str], timeout: float) -> dict[str, Any]:
    cli = (os.environ.get("ZINIAO_CLI_BIN") or "ziniao-cli").strip() or "ziniao-cli"
    executable = shutil.which(cli)
    if not executable:
        return {
            "ok": False,
            "data": None,
            "summary": f"未检测到紫鸟 CLI: {cli}",
            "error": "ziniao_cli_missing",
        }
    try:
        completed = subprocess.run(
            [executable, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "data": None, "summary": "紫鸟 CLI 超时", "error": "ziniao_cli_timeout"}
    except Exception as exc:
        return {"ok": False, "data": None, "summary": f"紫鸟 CLI 执行失败: {exc}", "error": str(exc)}
    output = (completed.stdout or completed.stderr or "").strip()
    ok = completed.returncode == 0
    return {
        "ok": ok,
        "data": output,
        "summary": _trim(output),
        "error": "" if ok else f"ziniao_cli_exit_{completed.returncode}",
    }


def ziniao_doctor(timeout: float = 20) -> dict[str, Any]:
    return _run_cli(["doctor"], _tool_timeout(timeout))


def ziniao_store_list(timeout: float = 30) -> dict[str, Any]:
    return _run_cli(["store", "list"], _tool_timeout(timeout))


def ziniao_store_open(store_id: str, url: str = "", timeout: float = 60) -> dict[str, Any]:
    args = ["store", "open", "--store-id", store_id]
    if url:
        args += ["--url", url]
    return _run_cli(args, _tool_timeout(timeout))


def ziniao_page_visit(
    store_id: str,
    url: str,
    wait_until: str = "domcontentloaded",
    timeout: float = 60,
) -> dict[str, Any]:
    return _run_cli(
        ["page", "visit", "--store-id", store_id, "--url", url, "--wait-until", wait_until],
        _tool_timeout(timeout),
    )


def ziniao_page_content(
    store_id: str,
    content_format: str = "structured",
    timeout: float = 60,
) -> dict[str, Any]:
    return _run_cli(
        ["page", "content", "--store-id", store_id, "--content-format", content_format],
        _tool_timeout(timeout),
    )


def ziniao_page_exec(store_id: str, js: str, timeout: float = 60) -> dict[str, Any]:
    return _run_cli(["page", "exec", "--store-id", store_id, "--js", js], _tool_timeout(timeout))


def ziniao_automation_run(steps_json: str, timeout: float = 120) -> dict[str, Any]:
    return _run_cli(["automation", "run", "--steps", steps_json], _tool_timeout(timeout))


def ziniao_page_screenshot(store_id: str, path: str, timeout: float = 60) -> dict[str, Any]:
    return _run_cli(["page", "screenshot", "--store-id", store_id, "--path", path], _tool_timeout(timeout))


def read_csv_file(path: str, max_rows: int = 200) -> dict[str, Any]:
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))[:max_rows]
    except FileNotFoundError:
        return {"ok": False, "data": [], "summary": "CSV 文件不存在", "error": "csv_not_found"}
    except Exception as exc:
        return {"ok": False, "data": [], "summary": f"CSV 读取失败: {exc}", "error": str(exc)}
    return {"ok": True, "data": rows, "summary": f"CSV {len(rows)} 行", "error": ""}
