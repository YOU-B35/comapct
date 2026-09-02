"""Platform-agnostic LLM agent loop with tool calling."""
from __future__ import annotations

import json
import os
from typing import Any, Callable

from app.llm.client import LlmResponse


def _max_tool_chars() -> int:
    try:
        return int(os.environ.get("AGENT_TOOL_RESULT_MAX_CHARS", "2000"))
    except ValueError:
        return 2000


def _max_rounds() -> int:
    try:
        return int(os.environ.get("AGENT_MAX_ROUNDS", "8"))
    except ValueError:
        return 8


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
    raw_limit = result.get("max_chars")
    limit = raw_limit if isinstance(raw_limit, int) and not isinstance(raw_limit, bool) else _max_tool_chars()
    limit = max(200, limit)
    return text[:limit] + ("..." if len(text) > limit else "")


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
    max_rounds = max(1, _max_rounds() if max_rounds is None else max_rounds)
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    if session_memory:
        messages.append({"role": "system", "content": f"店铺上下文与记忆：\n{session_memory}"})
    messages.append({"role": "user", "content": user_query})

    tool_logs: list[dict[str, Any]] = []
    usage_total: dict[str, int] = {}

    for _round in range(max_rounds):
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
            try:
                result = tool_executor(call.name, call.arguments)
            except Exception as exc:
                result = {"ok": False, "data": None, "summary": f"工具执行异常: {exc}", "error": str(exc)}
            tool_logs.append(
                {
                    "name": call.name,
                    "args": call.arguments,
                    "ok": bool(result.get("ok")),
                    "summary": str(result.get("summary") or ""),
                    "error": str(result.get("error") or ""),
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
            messages.append({"role": "tool", "tool_call_id": call.id, "content": _tool_payload(result)})

    return {
        "status": "max_rounds_exceeded",
        "answer": "",
        "tool_logs": tool_logs,
        "token_usage": usage_total,
        "error_message": "超过最大工具调用轮数，已停止",
    }
