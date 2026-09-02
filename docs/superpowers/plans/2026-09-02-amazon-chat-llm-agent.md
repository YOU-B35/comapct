# Amazon AI 助手接入大模型（LLM + 紫鸟 CLI 工具）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给现有 Amazon AI 助手（`amazon_chat` 任务通道）接入 DeepSeek 大模型与紫鸟 CLI 工具循环，让自然语言经营问题由 LLM 规划并执行紫鸟 CLI 工具实时取数，返回带来源/采集时间的答案；LLM 不可用时自动回退到现有 v1 确定性通道。

**Architecture:** 平台无关的 Agent 内核（LLM 循环 + 工具注册/分发）放在 `agent/chat_kernel.py`；DeepSeek（OpenAI 兼容 Chat Completions）客户端在 `app/llm/client.py`；紫鸟 CLI 工具薄封装在 `app/ziniao/cli_tools.py`；Amazon 适配层（system prompt、答案校验、记忆注入）与任务入口 `answer_amazon_chat` 在 `agent/amazon_chat_agent.py`。现有关键词边界过滤 `validate_boundary` 保留，作为 LLM 调用前的廉价拦截；`AMAZON_CHAT_LLM_ENABLED`/`LLM_API_KEY` 控制是否走 LLM 通道，失败即回退。

**Tech Stack:** Python 3.11 / httpx（与 `agent/java_client.py` 一致，不新增第三方依赖）/ DeepSeek Chat Completions（function calling）/ 紫鸟官方 CLI（`ziniao-cli`，可经 `ZINIAO_CLI_BIN` 覆盖）/ pytest（unittest 风格，与现有 `test_amazon_chat_agent.py` 一致）

## Global Constraints

- Python 3.11；HTTP 统一使用 httpx，禁止新增 requirements 依赖。
- LLM API Key 只允许经环境变量 `LLM_API_KEY` 注入，不得写入代码、日志或 git。
- 宁可不答、不编数据：LLM 最终答案必须包含「数据来源」与「采集时间」，否则视为校验失败。
- 写操作 / 跨平台 / 越权问题一律拒绝，复用现有 `validate_boundary`，LLM 通道不绕过。
- 工具输出进 LLM 前必须截断（默认单条 2000 字符），防止 token 失控。
- 默认不开启 LLM：未配置 `LLM_API_KEY` 且 `AMAZON_CHAT_LLM_ENABLED` 为空/0 时，行为与现在完全一致，`amazon_sync` 等旧通道不回归。
- 紫鸟 CLI 不存在或执行失败时，工具返回 `ok=False` 与中文摘要，不抛异常。
- 每次问答记录 `duration_ms` 与 `token_usage`，Java 侧已透传，前端已展示，无需改 Java/前端。

---

## File Structure

新建：

- `backend/python/app/llm/__init__.py` — 空包标记。
- `backend/python/app/llm/client.py` — LLM 客户端：环境变量解析、`chat_completion()`、响应解析（content/tool_calls/usage）。
- `backend/python/app/ziniao/cli_tools.py` — 紫鸟 CLI 工具薄封装：doctor / store list / store open / page visit / page content / page exec / automation run / page screenshot / csv_read，统一返回 `{"ok", "data", "summary", "error"}`。
- `backend/python/agent/agent_tools.py` — function-calling 工具 schema 列表 `TOOL_SCHEMAS` + `dispatch_tool(name, args)`。
- `backend/python/agent/chat_kernel.py` — 平台无关 LLM 循环：system prompt + 用户问题 → 反复调用 LLM → 执行工具 → 最终答案；含 max_rounds、token 汇总、工具日志。

修改：

- `backend/python/agent/amazon_chat_agent.py` — 新增 `llm_enabled()`、`build_amazon_system_prompt()`、`validate_llm_answer()`、`session_memory_text()`、`run_amazon_llm_chat()`；`answer_amazon_chat()` 在边界通过且 LLM 启用时优先走 LLM 通道，失败回退 v1。
- `backend/python/tests/test_amazon_chat_agent.py` — 追加 LLM 通道用例。
- `backend/python/.env.example` — 追加 `LLM_*` 与 `AMAZON_CHAT_LLM_ENABLED` 配置说明。

新建测试：

- `backend/python/tests/test_llm_client.py`
- `backend/python/tests/test_ziniao_cli_tools.py`
- `backend/python/tests/test_agent_tools.py`
- `backend/python/tests/test_chat_kernel.py`

## Task 1: LLM 客户端（`app/llm/client.py`）

**Files:**
- Create: `backend/python/app/llm/__init__.py`
- Create: `backend/python/app/llm/client.py`
- Test: `backend/python/tests/test_llm_client.py`

**Interfaces:**
- Consumes: 环境变量 `LLM_API_KEY` / `LLM_BASE_URL`（默认 `https://api.deepseek.com`）/ `LLM_MODEL`（默认 `deepseek-v4-flash-vision-exp`）/ `LLM_TIMEOUT_SECONDS`（默认 60）。
- Produces: `LlmToolCall(id: str, name: str, arguments: dict)`、`LlmResponse(content: str, tool_calls: list[LlmToolCall], usage: dict[str, int], model: str)`、`chat_completion(messages: list[dict], tools: list[dict] | None = None, model: str | None = None) -> LlmResponse`。Task 4 与 Task 5 依赖这些名字与字段。

- [ ] **Step 1: 写失败测试**

`backend/python/tests/test_llm_client.py`：

```python
from __future__ import annotations

import unittest
from unittest.mock import patch

from app.llm.client import LlmResponse, _parse_tool_calls, chat_completion


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


class FakeClient:
    def __init__(self, body):
        self._body = body
        self.posted = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, headers=None, json=None):
        self.posted = (url, headers, json)
        return FakeResponse(self._body)


class LlmClientTest(unittest.TestCase):
    def test_missing_api_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                chat_completion([{"role": "user", "content": "hi"}])
            self.assertIn("LLM_API_KEY", str(ctx.exception))

    def test_chat_completion_parses_text_and_usage(self):
        body = {
            "model": "deepseek-v4-flash-vision-exp",
            "choices": [{"message": {"role": "assistant", "content": "你好"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        fake = FakeClient(body)
        with patch.dict("os.environ", {"LLM_API_KEY": "sk-test"}, clear=True):
            with patch("app.llm.client.httpx.Client", return_value=fake):
                resp = chat_completion([{"role": "user", "content": "hi"}])
        self.assertEqual(resp.content, "你好")
        self.assertEqual(resp.usage["total_tokens"], 15)
        self.assertEqual(resp.model, "deepseek-v4-flash-vision-exp")
        self.assertEqual(fake.posted[2]["model"], "deepseek-v4-flash-vision-exp")

    def test_tool_call_arguments_json_parsed(self):
        calls = _parse_tool_calls(
            [
                {
                    "id": "call_1",
                    "function": {"name": "ziniao_page_content", "arguments": '{"store_id":"s1"}'},
                }
            ]
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "ziniao_page_content")
        self.assertEqual(calls[0].arguments, {"store_id": "s1"})

    def test_invalid_tool_call_arguments_become_empty_dict(self):
        calls = _parse_tool_calls(
            [{"id": "call_2", "function": {"name": "ziniao_page_visit", "arguments": "{broken"}}]
        )
        self.assertEqual(calls[0].arguments, {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

在 `backend/python` 目录运行：

```
python -m pytest tests/test_llm_client.py -v
```

预期：`ModuleNotFoundError: No module named 'app.llm'`（或 import 错误），测试因特性缺失失败。

- [ ] **Step 3: 实现最小代码**

`backend/python/app/llm/__init__.py`：空文件。

`backend/python/app/llm/client.py`：

```python
"""Minimal OpenAI-compatible Chat Completions client (DeepSeek) used by the LLM agent kernel."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash-vision-exp"


@dataclass(frozen=True)
class LlmToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LlmResponse:
    content: str
    tool_calls: list[LlmToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""


def llm_api_key() -> str:
    return (os.environ.get("LLM_API_KEY") or "").strip()


def llm_base_url() -> str:
    return (os.environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")


def llm_model() -> str:
    return (os.environ.get("LLM_MODEL") or DEFAULT_MODEL).strip()


def llm_timeout_seconds() -> float:
    try:
        return float(os.environ.get("LLM_TIMEOUT_SECONDS", "60"))
    except ValueError:
        return 60.0


def _headers() -> dict[str, str]:
    key = llm_api_key()
    if not key:
        raise RuntimeError("LLM_API_KEY 未配置，无法调用大模型")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _parse_tool_calls(raw: list[dict[str, Any]] | None) -> list[LlmToolCall]:
    calls: list[LlmToolCall] = []
    for item in raw or []:
        fn = item.get("function") or {}
        args = fn.get("arguments") or "{}"
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        calls.append(
            LlmToolCall(
                id=str(item.get("id") or ""),
                name=str(fn.get("name") or ""),
                arguments=args if isinstance(args, dict) else {},
            )
        )
    return calls


def chat_completion(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    model: str | None = None,
) -> LlmResponse:
    payload: dict[str, Any] = {
        "model": model or llm_model(),
        "messages": messages,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
    with httpx.Client(timeout=llm_timeout_seconds()) as client:
        resp = client.post(
            f"{llm_base_url()}/chat/completions",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
        body = resp.json()
    choice = (body.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    return LlmResponse(
        content=str(message.get("content") or ""),
        tool_calls=_parse_tool_calls(message.get("tool_calls")),
        usage=dict(body.get("usage") or {}),
        model=str(body.get("model") or ""),
    )
```

- [ ] **Step 4: 运行测试确认通过**

```
python -m pytest tests/test_llm_client.py -v
```

预期：4 passed。

- [ ] **Step 5: 提交**

```
git add backend/python/app/llm/__init__.py backend/python/app/llm/client.py backend/python/tests/test_llm_client.py
git commit -m "feat(llm): add OpenAI-compatible chat completion client with tool-call parsing"
```

## Task 2: 紫鸟 CLI 工具层（`app/ziniao/cli_tools.py`）

**Files:**
- Create: `backend/python/app/ziniao/cli_tools.py`
- Test: `backend/python/tests/test_ziniao_cli_tools.py`

**Interfaces:**
- Consumes: 环境变量 `ZINIAO_CLI_BIN`（默认 `ziniao-cli`）、`AMAZON_CHAT_TOOL_TIMEOUT_SECONDS`（默认 20）。
- Produces: `ziniao_doctor() / ziniao_store_list() / ziniao_store_open(store_id, url="") / ziniao_page_visit(store_id, url, wait_until="domcontentloaded") / ziniao_page_content(store_id, content_format="structured") / ziniao_page_exec(store_id, js) / ziniao_automation_run(steps_json) / ziniao_page_screenshot(store_id, path) / read_csv_file(path, max_rows=200)`。全部返回 `dict`，键固定为 `ok: bool, data: Any, summary: str, error: str`。Task 3 的 `dispatch_tool` 依赖这些签名与返回键。

- [ ] **Step 1: 写失败测试**

`backend/python/tests/test_ziniao_cli_tools.py`：

```python
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
    def test_missing_cli_returns_not_ok(self):
        with patch("app.ziniao.cli_tools.shutil.which", return_value=None):
            result = cli_tools.ziniao_doctor()
        self.assertFalse(result["ok"])
        self.assertIn("未检测到", result["summary"])

    def test_doctor_runs_cli_and_reports_ok(self):
        with patch("app.ziniao.cli_tools.shutil.which", return_value="C:\\bin\\ziniao-cli.exe"):
            with patch(
                "app.ziniao.cli_tools.subprocess.run",
                return_value=CompletedProc(0, "ziniao ok"),
            ) as run:
                result = cli_tools.ziniao_doctor()
        self.assertTrue(result["ok"])
        self.assertEqual(run.call_args[0][0], ["C:\\bin\\ziniao-cli.exe", "doctor"])
        self.assertIn("ziniao ok", result["summary"])

    def test_store_open_passes_store_id_and_url(self):
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

    def test_page_content_uses_structured_format(self):
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

    def test_read_csv_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "report.csv")
            with open(path, "w", newline="", encoding="utf-8") as fh:
                fh.write("asin,orders_30d\nB0TEST,5\n")
            result = cli_tools.read_csv_file(path)
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"][0]["asin"], "B0TEST")
        self.assertEqual(result["data"][0]["orders_30d"], "5")

    def test_read_csv_missing_file(self):
        result = cli_tools.read_csv_file("C:/no/such/file.csv")
        self.assertFalse(result["ok"])
        self.assertIn("不存在", result["summary"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

```
python -m pytest tests/test_ziniao_cli_tools.py -v
```

预期：`ModuleNotFoundError: No module named 'app.ziniao.cli_tools'`。

- [ ] **Step 3: 实现最小代码**

`backend/python/app/ziniao/cli_tools.py`：

```python
"""Ziniao official CLI thin wrappers used by the LLM agent tool layer."""
from __future__ import annotations

import csv
import os
import shutil
import subprocess
from typing import Any


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
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "data": None, "summary": f"紫鸟 CLI 执行失败: {exc}", "error": str(exc)}
    output = (completed.stdout or completed.stderr or "").strip()
    ok = completed.returncode == 0
    return {
        "ok": ok,
        "data": output,
        "summary": output[:2000] + ("..." if len(output) > 2000 else ""),
        "error": "" if ok else f"ziniao_cli_exit_{completed.returncode}",
    }


def _tool_timeout(default: float) -> float:
    try:
        return float(os.environ.get("AMAZON_CHAT_TOOL_TIMEOUT_SECONDS", str(default)))
    except ValueError:
        return default


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
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "data": [], "summary": f"CSV 读取失败: {exc}", "error": str(exc)}
    return {"ok": True, "data": rows, "summary": f"CSV {len(rows)} 行", "error": ""}
```

- [ ] **Step 4: 运行测试确认通过**

```
python -m pytest tests/test_ziniao_cli_tools.py -v
```

预期：6 passed。

- [ ] **Step 5: 提交**

```
git add backend/python/app/ziniao/cli_tools.py backend/python/tests/test_ziniao_cli_tools.py
git commit -m "feat(ziniao): add official CLI tool wrappers for LLM agent tool layer"
```

## Task 3: 工具 schema 与分发（`agent/agent_tools.py`）

**Files:**
- Create: `backend/python/agent/agent_tools.py`
- Test: `backend/python/tests/test_agent_tools.py`

**Interfaces:**
- Consumes: Task 2 的 `app.ziniao.cli_tools` 全部函数。
- Produces: `TOOL_SCHEMAS: list[dict]`（OpenAI function calling schema）、`dispatch_tool(name: str, args: dict) -> dict`（返回 Task 2 的 `{ok, data, summary, error}`）。Task 4 与 Task 5 依赖。

- [ ] **Step 1: 写失败测试**

`backend/python/tests/test_agent_tools.py`：

```python
from __future__ import annotations

import unittest
from unittest.mock import patch

from agent.agent_tools import TOOL_SCHEMAS, dispatch_tool


class AgentToolsTest(unittest.TestCase):
    def test_schemas_have_required_fields(self):
        self.assertGreaterEqual(len(TOOL_SCHEMAS), 8)
        for schema in TOOL_SCHEMAS:
            fn = schema["function"]
            self.assertIn("name", fn)
            self.assertIn("description", fn)
            self.assertIn("parameters", fn)
            self.assertTrue(fn["description"].strip())

    def test_unknown_tool_raises_key_error(self):
        with self.assertRaises(KeyError):
            dispatch_tool("no_such_tool", {})

    def test_dispatch_doctor(self):
        with patch(
            "agent.agent_tools.cli_tools.ziniao_doctor",
            return_value={"ok": True, "data": "ok", "summary": "ok", "error": ""},
        ) as mock_doctor:
            result = dispatch_tool("ziniao_doctor", {})
        mock_doctor.assert_called_once()
        self.assertTrue(result["ok"])

    def test_dispatch_store_open_passes_args(self):
        with patch(
            "agent.agent_tools.cli_tools.ziniao_store_open",
            return_value={"ok": True, "data": None, "summary": "opened", "error": ""},
        ) as mock_open:
            dispatch_tool("ziniao_store_open", {"store_id": "s1", "url": "https://sellercentral.amazon.com"})
        mock_open.assert_called_once_with("s1", "https://sellercentral.amazon.com")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

```
python -m pytest tests/test_agent_tools.py -v
```

预期：`ModuleNotFoundError: No module named 'agent.agent_tools'`。

- [ ] **Step 3: 实现最小代码**

`backend/python/agent/agent_tools.py`：

```python
"""LLM function-calling tool schemas + dispatch to Ziniao CLI wrappers."""
from __future__ import annotations

from typing import Any

from app.ziniao import cli_tools


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "ziniao_doctor",
            "description": "检查本机紫鸟客户端与登录态是否可用",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ziniao_store_list",
            "description": "列出紫鸟中已绑定且可用的店铺（含登录状态）",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ziniao_store_open",
            "description": "打开指定店铺的浏览器窗口，可带初始 URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "紫鸟店铺 ID"},
                    "url": {"type": "string", "description": "初始打开的 URL（可省略）"},
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
            "description": "让指定店铺浏览器导航到目标 URL",
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
            "description": "读取当前页面结构化内容（表格/列表优先），用于取经营数据",
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
            "description": "在店铺页面执行 JS（滚动、点击导出等），参数 js 为要执行的脚本",
            "parameters": {
                "type": "object",
                "properties": {
                    "store_id": {"type": "string"},
                    "js": {"type": "string"},
                },
                "required": ["store_id", "js"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ziniao_automation_run",
            "description": "执行多步浏览器编排（visit/click/exec），steps 为 JSON 步骤数组字符串",
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {"type": "string", "description": "JSON 数组字符串"},
                },
                "required": ["steps"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ziniao_page_screenshot",
            "description": "对当前店铺页面截图保存到 path",
            "parameters": {
                "type": "object",
                "properties": {
                    "store_id": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["store_id", "path"],
                "additionalProperties": False,
            },
        },
    },
]


def dispatch_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "ziniao_doctor":
        return cli_tools.ziniao_doctor()
    if name == "ziniao_store_list":
        return cli_tools.ziniao_store_list()
    if name == "ziniao_store_open":
        return cli_tools.ziniao_store_open(
            store_id=str(args.get("store_id") or ""),
            url=str(args.get("url") or ""),
        )
    if name == "ziniao_page_visit":
        return cli_tools.ziniao_page_visit(
            store_id=str(args.get("store_id") or ""),
            url=str(args.get("url") or ""),
            wait_until=str(args.get("wait_until") or "domcontentloaded"),
        )
    if name == "ziniao_page_content":
        return cli_tools.ziniao_page_content(
            store_id=str(args.get("store_id") or ""),
            content_format=str(args.get("content_format") or "structured"),
        )
    if name == "ziniao_page_exec":
        return cli_tools.ziniao_page_exec(
            store_id=str(args.get("store_id") or ""),
            js=str(args.get("js") or ""),
        )
    if name == "ziniao_automation_run":
        return cli_tools.ziniao_automation_run(steps_json=str(args.get("steps") or ""))
    if name == "ziniao_page_screenshot":
        return cli_tools.ziniao_page_screenshot(
            store_id=str(args.get("store_id") or ""),
            path=str(args.get("path") or ""),
        )
    raise KeyError(f"未知工具: {name}")
```

- [ ] **Step 4: 运行测试确认通过**

```
python -m pytest tests/test_agent_tools.py -v
```

预期：4 passed。

- [ ] **Step 5: 提交**

```
git add backend/python/agent/agent_tools.py backend/python/tests/test_agent_tools.py
git commit -m "feat(agent): add function-calling tool schemas and dispatch for ziniao CLI"
```

## Task 4: 平台无关 LLM 循环（`agent/chat_kernel.py`）

**Files:**
- Create: `backend/python/agent/chat_kernel.py`
- Test: `backend/python/tests/test_chat_kernel.py`

**Interfaces:**
- Consumes: Task 1 的 `LlmResponse` / `LlmToolCall`。
- Produces: `run_agent_loop(*, user_query: str, system_prompt: str, tools: list[dict], tool_executor: Callable[[str, dict], dict], llm: Callable[[list[dict], list[dict]], LlmResponse], max_rounds: int = 6, session_memory: str = "") -> dict`。返回键：`status`（`success` / `max_rounds_exceeded`）、`answer`、`tool_logs`（`[{name, args, ok, summary}]`）、`token_usage`（`dict[str, int]`）、`error_message`。Task 5 依赖。

- [ ] **Step 1: 写失败测试**

`backend/python/tests/test_chat_kernel.py`：

```python
from __future__ import annotations

import unittest

from agent.chat_kernel import run_agent_loop
from app.llm.client import LlmResponse, LlmToolCall


class FakeLlm:
    def __init__(self, script):
        self.script = list(script)
        self.seen_messages = []

    def __call__(self, messages, tools):
        self.seen_messages.append(messages)
        step = self.script.pop(0)
        return step(messages)


class ChatKernelTest(unittest.TestCase):
    def test_tool_then_answer(self):
        def first(messages):
            return LlmResponse(
                content="",
                tool_calls=[LlmToolCall(id="c1", name="ziniao_doctor", arguments={})],
            )

        def second(messages):
            return LlmResponse(
                content="工具可用。\n数据来源：ziniao doctor\n采集时间：2026-09-02 10:00:00"
            )

        executed = []

        def executor(name, args):
            executed.append((name, args))
            return {"ok": True, "data": {}, "summary": "ok"}

        result = run_agent_loop(
            user_query="查账户健康",
            system_prompt="rules",
            tools=[{}],
            tool_executor=executor,
            llm=FakeLlm([first, second]),
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("数据来源", result["answer"])
        self.assertEqual(executed, [("ziniao_doctor", {})])
        self.assertEqual(result["tool_logs"][0]["name"], "ziniao_doctor")

    def test_max_rounds_exceeded(self):
        def always_tool(messages):
            return LlmResponse(
                content="",
                tool_calls=[LlmToolCall(id="c1", name="ziniao_doctor", arguments={})],
            )

        result = run_agent_loop(
            user_query="q",
            system_prompt="p",
            tools=[{}],
            tool_executor=lambda n, a: {"ok": True, "data": {}, "summary": "ok"},
            llm=FakeLlm([always_tool] * 10),
            max_rounds=3,
        )
        self.assertEqual(result["status"], "max_rounds_exceeded")
        self.assertIn("超过", result["error_message"])

    def test_usage_accumulated_across_rounds(self):
        def first(m):
            return LlmResponse(
                content="",
                tool_calls=[LlmToolCall(id="c1", name="ziniao_doctor", arguments={})],
                usage={"total_tokens": 10},
            )

        def second(m):
            return LlmResponse(
                content="答案\n数据来源：x\n采集时间：y",
                usage={"total_tokens": 25},
            )

        result = run_agent_loop(
            user_query="q",
            system_prompt="p",
            tools=[{}],
            tool_executor=lambda n, a: {"ok": True, "data": {}, "summary": "ok"},
            llm=FakeLlm([first, second]),
        )
        self.assertEqual(result["token_usage"]["total_tokens"], 35)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

```
python -m pytest tests/test_chat_kernel.py -v
```

预期：`ModuleNotFoundError: No module named 'agent.chat_kernel'`。

- [ ] **Step 3: 实现最小代码**

`backend/python/agent/chat_kernel.py`：

```python
"""Platform-agnostic LLM agent loop: system prompt + tool calling until final answer."""
from __future__ import annotations

import json
from typing import Any, Callable

from app.llm.client import LlmResponse


def _accumulate(total: dict[str, int], usage: dict[str, int]) -> None:
    for key, value in (usage or {}).items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total[key] = int(total.get(key, 0)) + int(value)


def _tool_payload(result: dict[str, Any]) -> str:
    payload = {
        "ok": result.get("ok", False),
        "summary": result.get("summary", ""),
        "data": result.get("data"),
    }
    text = json.dumps(payload, ensure_ascii=False)
    return text[:2000] + ("..." if len(text) > 2000 else "")


def run_agent_loop(
    *,
    user_query: str,
    system_prompt: str,
    tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]],
    llm: Callable[[list[dict[str, Any]], list[dict[str, Any]]], LlmResponse],
    max_rounds: int = 6,
    session_memory: str = "",
) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    if session_memory:
        messages.append({"role": "system", "content": f"店铺长期记忆：\n{session_memory}"})
    messages.append({"role": "user", "content": user_query})

    tool_logs: list[dict[str, Any]] = []
    usage_total: dict[str, int] = {}

    for _ in range(max_rounds):
        resp = llm(messages, tools)
        _accumulate(usage_total, resp.usage)
        if not resp.tool_calls:
            return {
                "status": "success",
                "answer": resp.content,
                "tool_logs": tool_logs,
                "token_usage": usage_total,
                "error_message": "",
            }
        for call in resp.tool_calls:
            result = tool_executor(call.name, call.arguments)
            tool_logs.append(
                {
                    "name": call.name,
                    "args": call.arguments,
                    "ok": result.get("ok", False),
                    "summary": result.get("summary", ""),
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments, ensure_ascii=False),
                            },
                        }
                    ],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": _tool_payload(result),
                }
            )

    return {
        "status": "max_rounds_exceeded",
        "answer": "",
        "tool_logs": tool_logs,
        "token_usage": usage_total,
        "error_message": "超过最大工具调用轮数，已停止",
    }
```

- [ ] **Step 4: 运行测试确认通过**

```
python -m pytest tests/test_chat_kernel.py -v
```

预期：3 passed。

- [ ] **Step 5: 提交**

```
git add backend/python/agent/chat_kernel.py backend/python/tests/test_chat_kernel.py
git commit -m "feat(agent): add platform-agnostic LLM tool-calling loop"
```

## Task 5: Amazon 适配层与任务入口集成（`agent/amazon_chat_agent.py`）

**Files:**
- Modify: `backend/python/agent/amazon_chat_agent.py`（文件顶部 import 区；`answer_amazon_chat()` 内部；文件末尾追加新函数）
- Modify: `backend/python/tests/test_amazon_chat_agent.py`（顶部 import；`AmazonChatAgentTest` 末尾追加用例）

**Interfaces:**
- Consumes: Task 1 `chat_completion`、Task 3 `TOOL_SCHEMAS`/`dispatch_tool`、Task 4 `run_agent_loop`。
- Produces: `llm_enabled() -> bool`、`build_amazon_system_prompt(store_name: str) -> str`、`validate_llm_answer(answer: str) -> tuple[bool, str]`、`session_memory_text(payload: dict) -> str`、`run_amazon_llm_chat(*, question, store_name, payload, llm, tool_executor) -> dict`；`answer_amazon_chat` 返回结构保持不变（`status/refused/answer/source/captured_at/duration_ms/token_usage/tool_calls/session_id`）。

- [ ] **Step 1: 写失败测试（先追加到现有测试文件）**

在 `backend/python/tests/test_amazon_chat_agent.py` 顶部 import 区追加：

```python
from app.llm.client import LlmResponse
from agent.amazon_chat_agent import (
    answer_amazon_chat,
    llm_enabled,
    validate_llm_answer,
    validate_boundary,
)
```

在 `AmazonChatAgentTest` 类末尾追加：

```python
    def test_llm_enabled_returns_true_when_switch_on(self):
        with patch.dict("os.environ", {"AMAZON_CHAT_LLM_ENABLED": "1"}, clear=False):
            self.assertTrue(llm_enabled())

    def test_llm_enabled_off_without_key(self):
        with patch.dict("os.environ", {"AMAZON_CHAT_LLM_ENABLED": "", "LLM_API_KEY": ""}, clear=False):
            self.assertFalse(llm_enabled())

    def test_validate_llm_answer_requires_source_and_time(self):
        ok, why = validate_llm_answer("账户健康正常。")
        self.assertFalse(ok)
        self.assertIn("数据来源", why)
        ok, _ = validate_llm_answer("账户健康正常。\n数据来源：紫鸟 page content\n采集时间：2026-09-02 10:00:00")
        self.assertTrue(ok)

    def test_llm_path_returns_answer_and_usage(self):
        task = _task("帮我看一下当前店铺的账户健康")
        task["payload"]["browser_id"] = ""
        with patch.dict("os.environ", {"AMAZON_CHAT_LLM_ENABLED": "1"}, clear=False):
            with patch(
                "agent.amazon_chat_agent.chat_completion",
                return_value=LlmResponse(
                    content="账户健康正常。\n数据来源：紫鸟 page content\n采集时间：2026-09-02 10:00:00",
                    usage={"total_tokens": 12},
                ),
            ):
                result = answer_amazon_chat(task)
        self.assertEqual("success", result["status"])
        self.assertIn("数据来源", result["answer"])
        self.assertEqual(result["token_usage"]["total_tokens"], 12)
        self.assertEqual(result["source"]["name"], "amazon_chat_llm_v2")

    def test_llm_failure_falls_back_to_v1_snapshot(self):
        task = _task("帮我看一下当前店铺的账户健康")
        task["payload"]["data_snapshot"] = {
            "captured_at": "2026-09-01 10:00:00",
            "account_metrics": [
                {"metric_key": "late_shipment_rate", "metric_label": "迟发率", "status": "warning", "value_text": "3.1%"}
            ],
            "operational_items": [],
            "top_products": [],
        }
        with patch.dict("os.environ", {"AMAZON_CHAT_LLM_ENABLED": "1"}, clear=False):
            with patch("agent.amazon_chat_agent.chat_completion", side_effect=RuntimeError("LLM down")):
                result = answer_amazon_chat(task)
        self.assertEqual("success", result["status"])
        self.assertEqual("crosshub_local_amazon_tables", result["source"]["name"])
```

- [ ] **Step 2: 运行测试确认失败**

```
python -m pytest tests/test_amazon_chat_agent.py -v
```

预期：新用例失败（`ImportError`：`cannot import name 'llm_enabled'`），旧用例仍通过。

- [ ] **Step 3: 实现最小代码**

`backend/python/agent/amazon_chat_agent.py` 顶部 import 区追加：

```python
from agent.agent_tools import TOOL_SCHEMAS, dispatch_tool
from agent.chat_kernel import run_agent_loop
from app.llm.client import chat_completion
```

`answer_amazon_chat()` 中，在 `decision = validate_boundary(question)` 与 `captured_at = _now()` 之后、`if not decision.allowed:` 之前不修改；在 `if not decision.allowed:` 分支之后追加 LLM 通道（放在 `live = read_live_amazon_data(...)` 之前）：

```python
    if llm_enabled():
        try:
            llm_out = run_amazon_llm_chat(
                question=question,
                store_name=store_name,
                payload=payload,
                llm=chat_completion,
                tool_executor=dispatch_tool,
            )
        except Exception as exc:  # noqa: BLE001
            llm_out = {"status": "failed", "error_message": str(exc)}
        if llm_out.get("status") == "success":
            return {
                "status": "success",
                "refused": False,
                "answer": llm_out["answer"],
                "source": {
                    "type": "llm_agent",
                    "name": "amazon_chat_llm_v2",
                    "status": "ok",
                    "captured_at": _now(),
                },
                "captured_at": _now(),
                "duration_ms": _elapsed_ms(started),
                "token_usage": llm_out.get("token_usage") or {},
                "tool_calls": llm_out.get("tool_calls") or [],
                "session_id": session_id,
            }
        # LLM 不可用/失败：继续走 v1 确定性通道
```

`backend/python/agent/amazon_chat_agent.py` 文件末尾追加：

```python
def llm_enabled() -> bool:
    switch = os.environ.get("AMAZON_CHAT_LLM_ENABLED", "").strip().lower()
    if switch in ("1", "true", "yes", "on"):
        return True
    if switch in ("0", "false", "no", "off"):
        return False
    return bool(os.environ.get("LLM_API_KEY", "").strip())


def build_amazon_system_prompt(store_name: str) -> str:
    return (
        "你是 CrossHub 的 Amazon 店铺运营数据助手，只服务当前绑定的 Amazon 店铺。\n"
        f"当前店铺：{store_name or '未命名店铺'}。\n"
        "铁律：\n"
        "1. 只能使用提供的紫鸟 CLI 工具取数；不得编造订单、金额、库存、评价等任何经营数据。\n"
        "2. 工具没拿到数据时，如实回答“未获取到数据”，禁止推测或估算。\n"
        "3. 回答必须包含“数据来源”和“采集时间”两行；来源写实际使用的工具名和页面。\n"
        "4. 只回答 Amazon 账户健康、订单/发货、商品/库存/广告、买家消息、评价、Case 等经营问题；写操作、跨平台、闲聊一律拒绝。\n"
        "5. 一次只做一件事：先打开店铺，再访问页面，避免重复打开同一店铺。\n"
        "6. 长页面优先用 page content / csv_read 的结构化数据，不要贴原始 HTML。\n"
    )


def validate_llm_answer(answer: str) -> tuple[bool, str]:
    if not answer or not answer.strip():
        return False, "答案为空白"
    if "数据来源" not in answer:
        return False, "答案缺少“数据来源”标注"
    if "采集时间" not in answer:
        return False, "答案缺少“采集时间”标注"
    return True, ""


def session_memory_text(payload: dict[str, Any]) -> str:
    rows = payload.get("memory") or []
    if not rows:
        return ""
    lines = []
    for row in rows[:20]:
        key = row.get("mem_key") or row.get("key") or ""
        value = row.get("mem_value") or row.get("value") or ""
        if key or value:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def run_amazon_llm_chat(
    *,
    question: str,
    store_name: str,
    payload: dict[str, Any],
    llm,
    tool_executor,
) -> dict[str, Any]:
    result = run_agent_loop(
        user_query=question,
        system_prompt=build_amazon_system_prompt(store_name),
        tools=TOOL_SCHEMAS,
        tool_executor=tool_executor,
        llm=llm,
        session_memory=session_memory_text(payload),
    )
    if result["status"] != "success" or not result["answer"]:
        return {
            "status": "failed",
            "error_message": result.get("error_message") or "LLM 未返回有效答案",
        }
    ok, why = validate_llm_answer(result["answer"])
    if not ok:
        return {"status": "failed", "error_message": f"答案校验未通过：{why}"}
    return {
        "status": "success",
        "answer": result["answer"],
        "tool_calls": result["tool_logs"],
        "token_usage": result["token_usage"],
    }
```

- [ ] **Step 4: 运行测试确认通过**

```
python -m pytest tests/test_amazon_chat_agent.py -v
```

预期：全部通过（原有 6 个 + 新增 5 个 = 11 个）。

- [ ] **Step 5: 提交**

```
git add backend/python/agent/amazon_chat_agent.py backend/python/tests/test_amazon_chat_agent.py
git commit -m "feat(amazon): wire LLM agent channel into amazon_chat with v1 fallback"
```

## Task 6: 环境配置说明与全量回归

**Files:**
- Modify: `backend/python/.env.example`

**Interfaces:**
- Consumes: Task 1–5 全部产出。
- Produces: 可运行配置文档。

- [ ] **Step 1: 追加配置说明**

在 `backend/python/.env.example` 末尾追加：

```
# Amazon AI 助手 LLM 通道（DeepSeek，OpenAI 兼容接口；真实 Key 只放 .env，勿提交 git）
# 配置 LLM_API_KEY 即自动启用；AMAZON_CHAT_LLM_ENABLED=1 可强制启用（=0 强制关闭）
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash-vision-exp
LLM_TIMEOUT_SECONDS=60
AMAZON_CHAT_LLM_ENABLED=0

# LLM 工具层紫鸟 CLI（未安装时 LLM 通道自动回退到本地快照/v1）
# ZINIAO_CLI_BIN=ziniao-cli
```

- [ ] **Step 2: 运行全量测试确认无回归**

```
python -m pytest -q
```

预期：新增测试全部通过；仍只有既有的 4 个失败（`test_amazon_parsers` ×2、`test_deploy_worker_alignment` ×2，均为本计划前已存在、与本次改动无关）。

- [ ] **Step 3: 提交**

```
git add backend/python/.env.example
git commit -m "docs(amazon): document LLM channel env config for amazon chat"
```

## 运行方式（交付后手工验证）

1. 在 `backend/python/.env` 配置 `LLM_API_KEY`（真实 Key 不提交 git），必要时 `ZINIAO_CLI_BIN` 指向本机紫鸟 CLI。
2. 重启 Sync Helper（桌面助手），确认心跳在线。
3. Amazon 模块选择单个店铺，在「AI 助手」提问「帮我看一下当前店铺的账户健康」。
4. 预期：LLM 通道返回带「数据来源」与「采集时间」的答案；聊天框下方展示耗时与 Token 数。
5. 拔掉 `LLM_API_KEY` 或关闭 `AMAZON_CHAT_LLM_ENABLED` 后重启，确认回退到 v1 快照/未获取数据行为。

## Self-Review

**Spec coverage（对照设计文档 `docs/superpowers/specs/2026-09-01-amazon-chat-llm-agent-design.md`）：**

- LLM 循环 + function calling：Task 4 ✅
- DeepSeek 接入（OpenAI 兼容、可配置模型/超时）：Task 1 ✅
- 紫鸟 CLI 工具层（doctor/store/page/automation/screenshot/csv）：Task 2、Task 3 ✅
- 边界管理（写操作/跨平台/白名单拦截）：复用现有 `validate_boundary`，Task 5 集成不变 ✅
- 答案校验（来源 + 时间强制标注）：Task 5 `validate_llm_answer` ✅
- 记忆注入（短期会话 + 店铺长期记忆只读带入）：Task 5 `session_memory_text`（写回记忆留待二期，符合设计文档 v1 范围）✅
- 耗时/token 统计：Task 4 汇总 + Java 已透传 ✅
- 旧通道回归不破坏：Task 6 全量回归 + `llm_enabled()` 默认关闭 ✅

**Placeholder scan：** 无 TBD/TODO/「自行处理」类步骤；每个代码步骤都给了完整代码与预期输出。

**Type consistency：** `LlmResponse.content/tool_calls/usage/model`、`LlmToolCall.id/name/arguments`、工具返回 `{ok, data, summary, error}`、`run_agent_loop` 返回键 `status/answer/tool_logs/token_usage/error_message`、`answer_amazon_chat` 返回结构在各任务间一致，无跨任务改名。
