"""OpenAI-compatible Chat Completions client used by the agent kernel."""
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
        args: Any = fn.get("arguments") or "{}"
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
        model=str(body.get("model") or payload["model"]),
    )
