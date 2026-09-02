from __future__ import annotations

import unittest
from unittest.mock import patch

from app.llm.client import _parse_tool_calls, chat_completion


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
    def test_missing_api_key_raises(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                chat_completion([{"role": "user", "content": "hi"}])
        self.assertIn("LLM_API_KEY", str(ctx.exception))

    def test_chat_completion_parses_text_and_usage(self) -> None:
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

    def test_tool_call_arguments_json_parsed(self) -> None:
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

    def test_invalid_tool_call_arguments_become_empty_dict(self) -> None:
        calls = _parse_tool_calls(
            [{"id": "call_2", "function": {"name": "ziniao_page_visit", "arguments": "{broken"}}]
        )
        self.assertEqual(calls[0].arguments, {})


if __name__ == "__main__":
    unittest.main()
