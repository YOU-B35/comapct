# Amazon AI 助手实时取数（LLM + 紫鸟 CLI）数据提取完善实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Amazon AI 助手在 LLM + 紫鸟 CLI 实时取数链路里，能真正读出经营数据（先以账户健康为验证场景），回答不再只是「未获取到数据」或菜单文本。

**Architecture:** 复用已合并的 LLM Agent 内核（`agent/chat_kernel.py`）与紫鸟 CLI 工具层（`app/ziniao/cli_tools.py`）。三处针对性完善：① 页面内容工具结果放宽截断（按工具支持 `max_chars`）；② 修正账户健康页 URL 并在 system prompt 中给出页面 URL 地图与 `page exec` 定向提取脚本；③ 工具轮数上限改为环境变量可配。最后用真实店铺跑端到端验证。

**Tech Stack:** Python 3.11 / pytest（unittest 风格）/ ziniao-cli（`tools/ziniao-cli`，npm 包 `@ziniao-open/cli`）/ DeepSeek Chat Completions（`LLM_API_KEY` 已配置）

## Global Constraints

- 复用现有 `app/ziniao/cli_tools.py` 的 `{ok, data, summary, error}` 返回契约，不改 CLI 命令名。
- 工具结果进 LLM 前必须截断（`chat_kernel._tool_payload`），不得把整页 HTML 全量塞进对话；放宽只针对 `page content` 的文本/结构化数据，默认上限 12000 字符，可经环境变量调整。
- 宁缺毋滥：LLM 答案必须带「数据来源」与「采集时间」，拿不到数据就明说「未获取到数据」。
- 只读问答：不新增写操作工具；跨平台/写操作仍由现有 `validate_boundary` 拒绝。
- 不破坏 v1 确定性通道（`AMAZON_CHAT_LLM_ENABLED=0` 时行为不变），`amazon_sync` 旧通道不动。
- 命令都在 `backend/python` 目录下执行；已知全量测试里有 4 个与本次无关的既有失败（`test_amazon_parsers` ×2、`test_deploy_worker_alignment` ×2），验收时只要求新增/相关用例通过且失败集合不扩大。

---

## 背景（为什么做这些改动）

2026-09-02 端到端实测（YOTO美国账号，storeId `16505337258263`，问题「帮我看一下当前店铺的账户健康」）：

1. LLM 调用 `ziniao_store_open` → 店铺浏览器打开成功（`reused: true`）。
2. LLM 调用 `ziniao_page_visit https://sellercentral.amazon.com/account-health` → 导航成功，但该 URL 实际不是账户健康页（正确地址是 `/performance/account/health`）。
3. LLM 调用 `ziniao_page_content --content-format structured/text` → 返回的是后台左侧菜单文本；账户健康指标位于页面下方，被 `chat_kernel._tool_payload` 的 2000 字符截断挡在 LLM 视野之外。
4. 6 轮工具调用后仍未得到最终答案，`run_agent_loop` 返回 `max_rounds_exceeded`，`answer_amazon_chat` 回退到 v1「未获取到数据」。

因此剩余工作 = 修正 URL + 放宽页面内容截断 + 给 LLM 明确的页面提取指引 + 轮数可配 + 端到端验收。

## File Structure

修改：

- `backend/python/agent/chat_kernel.py` — `_tool_payload` 支持工具结果携带 `max_chars`；`run_agent_loop` 的 `max_rounds` 支持环境变量默认值。
- `backend/python/app/ziniao/cli_tools.py` — `ziniao_page_content` 返回 `max_chars`（默认 12000，`AGENT_PAGE_CONTENT_MAX_CHARS` 可调）。
- `backend/python/agent/amazon_chat_agent.py` — `build_amazon_system_prompt` 增加页面 URL 地图与账户健康指标提取指引（含 `page exec` JS）。
- `backend/python/.env.example` — 新增 `AGENT_TOOL_RESULT_MAX_CHARS` / `AGENT_PAGE_CONTENT_MAX_CHARS` / `AGENT_MAX_ROUNDS` 说明。

修改测试：

- `backend/python/tests/test_chat_kernel.py`
- `backend/python/tests/test_ziniao_cli_tools.py`
- `backend/python/tests/test_amazon_chat_agent.py`

## Task 1: 工具结果截断按工具放宽（`chat_kernel.py` + `cli_tools.py`）

**Files:**
- Modify: `backend/python/agent/chat_kernel.py`（`_tool_payload`）
- Modify: `backend/python/app/ziniao/cli_tools.py`（`ziniao_page_content`）
- Test: `backend/python/tests/test_chat_kernel.py`、`backend/python/tests/test_ziniao_cli_tools.py`

**Interfaces:**
- Consumes: 工具结果 dict（现有 `{ok, data, summary, error}`）。
- Produces: `_tool_payload(result)` 支持可选 `result["max_chars"]: int`；`ziniao_page_content` 返回结果含 `max_chars`。Task 4 的端到端验证依赖页面内容能带足量文本。

- [ ] **Step 1: 写失败测试**

在 `backend/python/tests/test_chat_kernel.py` 追加：

```python
    def test_tool_payload_honors_result_max_chars(self) -> None:
        from agent.chat_kernel import _tool_payload

        payload = _tool_payload(
            {
                "ok": True,
                "summary": "ok",
                "data": "x" * 5000,
                "max_chars": 3000,
            }
        )
        self.assertLessEqual(len(payload), 3100)
        self.assertIn("...", payload)

    def test_tool_payload_default_limit_without_max_chars(self) -> None:
        from agent.chat_kernel import _tool_payload

        payload = _tool_payload({"ok": True, "summary": "ok", "data": "y" * 5000})
        self.assertLessEqual(len(payload), 2100)
```

在 `backend/python/tests/test_ziniao_cli_tools.py` 追加：

```python
    def test_page_content_result_carries_max_chars(self) -> None:
        with patch("app.ziniao.cli_tools.shutil.which", return_value="ziniao-cli"):
            with patch(
                "app.ziniao.cli_tools.subprocess.run",
                return_value=CompletedProc(0, '{"ok": true, "data": {"content": "abc"}}'),
            ) as run:
                result = cli_tools.ziniao_page_content("s1")
        self.assertTrue(result["ok"])
        self.assertIsInstance(result.get("max_chars"), int)
        self.assertGreaterEqual(result["max_chars"], 12000)
```

- [ ] **Step 2: 运行测试确认失败**

```
python -m pytest tests/test_chat_kernel.py tests/test_ziniao_cli_tools.py -v
```

预期：新增用例失败（`_tool_payload` 未读 `max_chars`；`ziniao_page_content` 结果无 `max_chars`）。

- [ ] **Step 3: 实现最小代码**

`backend/python/agent/chat_kernel.py` 的 `_tool_payload` 改为：

```python
def _tool_payload(result: dict[str, Any]) -> str:
    payload = {
        "ok": result.get("ok", False),
        "summary": result.get("summary", ""),
        "data": result.get("data"),
    }
    text = json.dumps(payload, ensure_ascii=False)
    raw_max = result.get("max_chars")
    limit = int(raw_max) if isinstance(raw_max, int) and raw_max > 0 else _max_tool_chars()
    limit = max(200, limit)
    return text[:limit] + ("..." if len(text) > limit else "")
```

`backend/python/app/ziniao/cli_tools.py` 新增并修改：

```python
def _page_content_max_chars() -> int:
    try:
        return int(os.environ.get("AGENT_PAGE_CONTENT_MAX_CHARS", "12000"))
    except ValueError:
        return 12000


def ziniao_page_content(
    store_id: str,
    content_format: str = "structured",
    timeout: float = 60,
) -> dict[str, Any]:
    result = _run_cli(
        ["page", "content", "--store-id", store_id, "--content-format", content_format],
        _tool_timeout(timeout),
    )
    if result["ok"]:
        result["max_chars"] = _page_content_max_chars()
    return result
```

- [ ] **Step 4: 运行测试确认通过**

```
python -m pytest tests/test_chat_kernel.py tests/test_ziniao_cli_tools.py -v
```

预期：全部通过。

- [ ] **Step 5: 提交**

```
git add backend/python/agent/chat_kernel.py backend/python/app/ziniao/cli_tools.py backend/python/tests/test_chat_kernel.py backend/python/tests/test_ziniao_cli_tools.py
git commit -m "feat(agent): allow per-tool tool-result char budget for page content"
```

## Task 2: 账户健康 URL 修正与 system prompt 提取指引（`amazon_chat_agent.py`）

**Files:**
- Modify: `backend/python/agent/amazon_chat_agent.py`（`build_amazon_system_prompt`）
- Test: `backend/python/tests/test_amazon_chat_agent.py`

**Interfaces:**
- Consumes: 现有 `build_amazon_system_prompt(store_name)`。
- Produces: prompt 中新增「页面 URL 地图」与「账户健康指标提取 JS」。Task 4 端到端验证依赖模型按正确 URL 导航并用 `page exec` 提取。

- [ ] **Step 1: 写失败测试**

在 `backend/python/tests/test_amazon_chat_agent.py` 的 `AmazonChatAgentTest` 追加：

```python
    def test_system_prompt_contains_account_health_url_and_extract_js(self) -> None:
        prompt = build_amazon_system_prompt("YOTO美国账号")
        self.assertIn("performance/account/health", prompt)
        self.assertIn("page exec", prompt)
        self.assertIn("订单缺陷率", prompt)
```

- [ ] **Step 2: 运行测试确认失败**

```
python -m pytest tests/test_amazon_chat_agent.py::AmazonChatAgentTest::test_system_prompt_contains_account_health_url_and_extract_js -v
```

预期：FAIL（prompt 不含这些内容）。

- [ ] **Step 3: 实现最小代码**

`build_amazon_system_prompt` 在规则 7 之后追加规则 8、9：

```python
        "8. 页面 URL 地图：账户健康=https://sellercentral.amazon.com/performance/account/health；"
        "订单=https://sellercentral.amazon.com/orders-v3/?page=1；"
        "商品报告=https://sellercentral.amazon.com/business-reports/detail/sales-traffic-by-asin；"
        "库存=https://sellercentral.amazon.com/myinventory/inventory。不要臆造 URL。\n"
        "9. 账户健康页若 text 只有左侧菜单、没有指标数值，用 page exec 执行下面 JS 提取指标区文本，"
        "禁止只凭菜单就下结论："
        "(()=>{const b=document.body.innerText;const i=b.indexOf('账户状况');"
        "return i>=0?b.slice(Math.max(0,i-200),i+4000):b.slice(0,4000)})()\n"
    )
```

- [ ] **Step 4: 运行测试确认通过**

```
python -m pytest tests/test_amazon_chat_agent.py -v
```

预期：全部通过（含既有用例）。

- [ ] **Step 5: 提交**

```
git add backend/python/agent/amazon_chat_agent.py backend/python/tests/test_amazon_chat_agent.py
git commit -m "feat(amazon): teach LLM correct account-health URL and page exec extraction"
```

## Task 3: 工具轮数上限可配置（`chat_kernel.py`）

**Files:**
- Modify: `backend/python/agent/chat_kernel.py`（`run_agent_loop` 默认值）
- Test: `backend/python/tests/test_chat_kernel.py`

**Interfaces:**
- Consumes: 环境变量 `AGENT_MAX_ROUNDS`（默认 8）。
- Produces: `run_agent_loop(..., max_rounds: int | None = None)`。

- [ ] **Step 1: 写失败测试**

在 `backend/python/tests/test_chat_kernel.py` 追加：

```python
    def test_max_rounds_reads_env_default(self) -> None:
        from unittest.mock import patch

        def always_tool(messages):
            return LlmResponse(
                content="",
                tool_calls=[LlmToolCall(id="c1", name="ziniao_doctor", arguments={})],
            )

        with patch.dict("os.environ", {"AGENT_MAX_ROUNDS": "2"}, clear=False):
            result = run_agent_loop(
                user_query="q",
                system_prompt="p",
                tools=[{}],
                tool_executor=lambda n, a: {"ok": True, "data": {}, "summary": "ok"},
                llm=FakeLlm([always_tool] * 10),
            )
        self.assertEqual(result["status"], "max_rounds_exceeded")
        self.assertEqual(len(result["tool_logs"]), 2)
```

- [ ] **Step 2: 运行测试确认失败**

```
python -m pytest tests/test_chat_kernel.py::ChatKernelTest::test_max_rounds_reads_env_default -v
```

预期：FAIL（当前默认固定 6，2 轮后不会停止，`tool_logs` 长度 ≠ 2）。

- [ ] **Step 3: 实现最小代码**

`run_agent_loop` 签名与函数体开头改为：

```python
def run_agent_loop(
    *,
    user_query: str,
    system_prompt: str,
    tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]],
    llm: Callable[[list[dict[str, Any]], list[dict[str, Any]]], LlmResponse],
    max_rounds: int | None = None,
    session_memory: str = "",
) -> dict[str, Any]:
    if max_rounds is None:
        try:
            max_rounds = int(os.environ.get("AGENT_MAX_ROUNDS", "8"))
        except ValueError:
            max_rounds = 8
    max_rounds = max(1, max_rounds)
```

（其余逻辑不变，循环仍使用 `range(max_rounds)`。）

- [ ] **Step 4: 运行测试确认通过**

```
python -m pytest tests/test_chat_kernel.py -v
```

预期：全部通过。

- [ ] **Step 5: 提交**

```
git add backend/python/agent/chat_kernel.py backend/python/tests/test_chat_kernel.py
git commit -m "feat(agent): make agent max tool rounds configurable via env"
```

## Task 4: 环境变量文档与端到端验收

**Files:**
- Modify: `backend/python/.env.example`

**Interfaces:**
- Consumes: Task 1–3 全部产出。
- Produces: 可运行配置说明 + 验收步骤。

- [ ] **Step 1: 在 `.env.example` 追加配置说明**

```
# Amazon AI 助手 LLM Agent 参数（可选）
# 工具结果进 LLM 的默认字符上限（默认 2000）
# AGENT_TOOL_RESULT_MAX_CHARS=2000
# page content 工具结果字符上限（默认 12000；账户健康页指标较长时适当调大）
# AGENT_PAGE_CONTENT_MAX_CHARS=12000
# LLM 工具调用最大轮数（默认 8）
# AGENT_MAX_ROUNDS=8
```

- [ ] **Step 2: 运行相关测试与全量回归**

```
python -m pytest tests/test_chat_kernel.py tests/test_ziniao_cli_tools.py tests/test_amazon_chat_agent.py -q
python -m pytest -q
```

预期：相关用例全部通过；全量仅剩既有的 4 个失败（`test_amazon_parsers` ×2、`test_deploy_worker_alignment` ×2），失败集合不扩大。

- [ ] **Step 3: 端到端验收（真实店铺 + 真实 LLM）**

1. 确认 `tools/ziniao-cli` 已安装（`npm install`）且授权有效：`ziniao-cli doctor` 全绿。
2. 确认 `backend/python/.env` 有 `LLM_API_KEY` 与 `ZINIAO_CLI_BIN`，并重启 Sync Helper（日志出现 `已加载 .env: ...\backend\python\.env`）。
3. 用以下临时脚本（放在 `_scratch/`，不入库）跑真实问答：

```python
import os

from agent.amazon_chat_agent import answer_amazon_chat, llm_enabled


def load_project_env():
    path = r"D:\YOTO-SASS\SaaS-HZ_WEB_Demo\backend\python\.env"
    for line in open(path, encoding="utf-8"):
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, _, value = text.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


load_project_env()
print("llm_enabled:", llm_enabled())

task = {
    "task_id": "amz_chat_task_e2e",
    "payload": {
        "message": "帮我看一下当前店铺的账户健康",
        "store_name": "YOTO美国账号",
        "platform_account_id": "e2e-store",
        "browser_id": "16505337258263",
        "merchant_id": "",
        "session_id": "amz_chat_sess_e2e",
        "memory": [],
        "data_snapshot": {},
    },
}
result = answer_amazon_chat(task)
print("status:", result["status"])
print("answer:", result["answer"][:1000])
print("source:", result.get("source"))
print("token_usage:", result.get("token_usage"))
```

4. 验收标准：`status == "success"`，答案包含真实账户健康指标（如「订单缺陷率」「迟发率」或对应数值），且包含「数据来源」与「采集时间」；`tool_calls` 里应能看到 `ziniao_page_visit`（URL 为 `/performance/account/health`）与 `ziniao_page_content`/`ziniao_page_exec`。
5. 如果指标仍读不出：在紫鸟打开 YOTO美国账号后，手动执行一次
   `ziniao-cli page exec --store-id 16505337258263 --script "(()=>{const b=document.body.innerText;const i=b.indexOf('账户状况');return i>=0?b.slice(Math.max(0,i-200),i+4000):b.slice(0,4000)})()"`
   核对返回文本里是否有指标数值；若没有，说明页面登录态或指标区结构变化，调整 JS 提取起点/长度后重跑验收。

- [ ] **Step 4: 提交**

```
git add backend/python/.env.example
git commit -m "docs(amazon): document agent tool budget and rounds env config"
```

## 运行方式（同事拿到后的环境准备）

1. `git pull`，在 `tools/ziniao-cli` 下执行 `npm install`（node_modules 不入库）。
2. 确认 `ziniao-cli doctor` 全绿（配置在 `C:\Users\Administrator\.ziniao-cli\config.json`，profile xuquan，apiKey 静态不过期）。
3. 确认 `backend/python/.env` 含 `LLM_API_KEY`、`ZINIAO_CLI_BIN`（指向 `tools/ziniao-cli\node_modules\.bin\ziniao-cli.cmd`）、紫鸟 `ZINIAO_*`。
4. 重启 Sync Helper（`taskkill /F /PID <旧PID>` 后用 `python -u backend/python/scripts/sync_helper_app.py` 从项目根启动），日志需出现 `已加载 .env: ...\backend\python\.env`。
5. 按 Task 4 端到端验收跑真实问答。

## Self-Review

**Spec coverage（对照 2026-09-02 实测发现的问题）：**

- 2000 字符截断导致指标不可见 → Task 1（`max_chars` 按工具放宽）✅
- 账户健康 URL 错误（`/account-health`、`/account/health`）→ Task 2（正确 URL `/performance/account/health` 写入 prompt）✅
- 页面只有菜单、没有指标 → Task 2（`page exec` 提取 JS + 禁止仅凭菜单下结论）✅
- 6 轮工具调用不够 → Task 3（`AGENT_MAX_ROUNDS` 默认 8）✅
- 端到端验收与指标核对 → Task 4 ✅

**Placeholder scan：** 无 TBD/TODO；JS 提取脚本给了可执行版本，并注明若结构变化如何调整。

**Type consistency：** `max_chars` 在 `cli_tools` 结果与 `chat_kernel._tool_payload` 中的读取一致（`int`）；`run_agent_loop` 的 `max_rounds` 参数语义不变（`None` → env → 默认 8）；`answer_amazon_chat` 返回结构未改动。
