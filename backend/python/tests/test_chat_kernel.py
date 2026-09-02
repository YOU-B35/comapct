from __future__ import annotations

import unittest
from unittest.mock import patch

from agent.chat_kernel import _tool_payload, run_agent_loop
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
    def test_tool_then_answer(self) -> None:
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

    def test_max_rounds_exceeded(self) -> None:
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

    def test_usage_accumulated_across_rounds(self) -> None:
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

    def test_tool_payload_honors_result_max_chars(self) -> None:
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

    def test_tool_payload_uses_default_limit_without_max_chars(self) -> None:
        payload = _tool_payload({"ok": True, "summary": "ok", "data": "y" * 5000})

        self.assertLessEqual(len(payload), 2100)

    def test_max_rounds_reads_env_default(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
