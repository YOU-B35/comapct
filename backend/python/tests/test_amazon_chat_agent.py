from __future__ import annotations

import unittest
from unittest.mock import patch

from agent.amazon_chat_agent import (
    amazon_tool_executor,
    answer_amazon_chat,
    build_amazon_system_prompt,
    infer_amazon_scope,
    llm_enabled,
    validate_boundary,
    validate_llm_answer,
)
from app.llm.client import LlmResponse


def _task(message: str) -> dict:
    return {
        "task_id": "amz_chat_task_test",
        "payload": {
            "message": message,
            "store_name": "US Test Store",
            "platform_account_id": "amz_store_1",
            "session_id": "amz_chat_sess_test",
        },
    }


class AmazonChatAgentTest(unittest.TestCase):
    def test_rejects_cross_platform_question(self) -> None:
        decision = validate_boundary("帮我查一下拼多多的订单情况")

        self.assertFalse(decision.allowed)
        self.assertEqual("AMAZON_CHAT_CROSS_PLATFORM_REFUSED", decision.error_code)

    def test_rejects_write_action(self) -> None:
        decision = validate_boundary("帮我回复买家并发送消息")

        self.assertFalse(decision.allowed)
        self.assertEqual("AMAZON_CHAT_WRITE_REFUSED", decision.error_code)

    def test_no_tool_returns_no_live_data(self) -> None:
        with patch.dict(
            "os.environ",
            {"ZINIAO_CLI_BIN": "__missing_ziniao_cli__", "AMAZON_CHAT_LLM_ENABLED": "0"},
        ):
            result = answer_amazon_chat(_task("帮我看一下当前店铺的账户健康"))

        self.assertEqual("no_live_data", result["status"])
        self.assertFalse(result["refused"])
        self.assertIn("不会生成经营结论", result["answer"])
        self.assertEqual("missing", result["source"]["status"])
        self.assertTrue(result["captured_at"])
        self.assertGreaterEqual(result["duration_ms"], 0)

    def test_read_only_shipping_question_is_allowed(self) -> None:
        decision = validate_boundary("当前店铺有哪些订单或发货事项需要今天优先跟进？")

        self.assertTrue(decision.allowed)

    def test_snapshot_data_returns_database_source(self) -> None:
        task = _task("帮我看一下当前店铺的账户健康")
        task["payload"]["data_snapshot"] = {
            "captured_at": "2026-09-01 10:00:00",
            "account_metrics": [
                {
                    "metric_key": "late_shipment_rate",
                    "metric_label": "迟发率",
                    "status": "warning",
                    "value_text": "3.1%",
                }
            ],
            "operational_items": [],
            "top_products": [],
        }

        with patch.dict("os.environ", {"AMAZON_CHAT_LLM_ENABLED": "0"}, clear=False):
            result = answer_amazon_chat(task)

        self.assertEqual("success", result["status"])
        self.assertIn("迟发率", result["answer"])
        self.assertEqual("crosshub_local_amazon_tables", result["source"]["name"])

    def test_ziniao_binding_uses_live_crawl_before_snapshot(self) -> None:
        task = _task("帮我看一下当前店铺的账户健康")
        task["payload"]["browser_id"] = "browser-1"
        task["payload"]["data_snapshot"] = {
            "captured_at": "2026-09-01 10:00:00",
            "account_metrics": [
                {"metric_key": "cached", "metric_label": "缓存指标", "status": "warning", "value_text": "1"}
            ],
            "operational_items": [],
            "top_products": [],
        }

        with patch(
            "agent.amazon_chat_agent.crawl_amazon",
            return_value={
                "metrics": [{"metric_key": "live", "label": "实时指标", "status": "normal", "value": "0"}],
                "result_summary": {"products_count": 0, "orders_count": 0},
            },
        ):
            with patch.dict("os.environ", {"AMAZON_CHAT_LLM_ENABLED": "0"}, clear=False):
                result = answer_amazon_chat(task)

        self.assertEqual("success", result["status"])
        self.assertIn("实时指标", result["answer"])
        self.assertNotIn("缓存指标", result["answer"])
        self.assertEqual("ziniao_browser:account_health", result["source"]["name"])

    def test_llm_enabled_returns_true_when_switch_on(self) -> None:
        with patch.dict("os.environ", {"AMAZON_CHAT_LLM_ENABLED": "1"}, clear=False):
            self.assertTrue(llm_enabled())

    def test_llm_enabled_off_without_key(self) -> None:
        with patch.dict("os.environ", {"AMAZON_CHAT_LLM_ENABLED": "", "LLM_API_KEY": ""}, clear=False):
            self.assertFalse(llm_enabled())

    def test_validate_llm_answer_requires_source_and_time(self) -> None:
        ok, why = validate_llm_answer("账户健康正常。")
        self.assertFalse(ok)
        self.assertIn("数据来源", why)
        ok, _ = validate_llm_answer("账户健康正常。\n数据来源：紫鸟 page content\n采集时间：2026-09-02 10:00:00")
        self.assertTrue(ok)

    def test_llm_path_returns_answer_and_usage(self) -> None:
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

    def test_llm_failure_falls_back_to_v1_snapshot(self) -> None:
        task = _task("帮我看一下当前店铺的账户健康")
        task["payload"]["data_snapshot"] = {
            "captured_at": "2026-09-01 10:00:00",
            "account_metrics": [
                {
                    "metric_key": "late_shipment_rate",
                    "metric_label": "迟发率",
                    "status": "warning",
                    "value_text": "3.1%",
                }
            ],
            "operational_items": [],
            "top_products": [],
        }
        with patch.dict("os.environ", {"AMAZON_CHAT_LLM_ENABLED": "1"}, clear=False):
            with patch("agent.amazon_chat_agent.chat_completion", side_effect=RuntimeError("LLM down")):
                result = answer_amazon_chat(task)
        self.assertEqual("success", result["status"])
        self.assertEqual("crosshub_local_amazon_tables", result["source"]["name"])

    def test_llm_tool_executor_rejects_other_store(self) -> None:
        calls = []

        def executor(name, args):
            calls.append((name, args))
            return {"ok": True, "data": None, "summary": "opened", "error": ""}

        guarded = amazon_tool_executor({"browser_id": "current-store"}, executor)
        result = guarded("ziniao_store_open", {"store_id": "other-store"})

        self.assertFalse(result["ok"])
        self.assertEqual("amazon_chat_store_mismatch", result["error"])
        self.assertEqual([], calls)

    def test_system_prompt_guides_using_bound_store(self) -> None:
        prompt = build_amazon_system_prompt("YOTO美国账号")
        self.assertIn("YOTO美国账号", prompt)
        self.assertIn("绑定", prompt)
        self.assertIn("storeId", prompt)
        self.assertIn("ziniao_store_list", prompt)

    def test_system_prompt_contains_account_health_url_and_extract_js(self) -> None:
        prompt = build_amazon_system_prompt("YOTO美国账号")

        self.assertIn("performance/dashboard", prompt)
        self.assertIn("performance/account/health", prompt)
        self.assertIn("page exec", prompt)
        self.assertIn("订单缺陷率", prompt)

    def test_sales_questions_are_allowed(self) -> None:
        for question in (
            "帮我查一下今天店铺卖了多少钱",
            "今天销售额是多少",
            "店铺今天一共卖了多少钱",
            "查一下最近7天的销售和收入",
        ):
            decision = validate_boundary(question)
            self.assertTrue(decision.allowed, question)
            self.assertEqual("", decision.error_code, question)

    def test_sales_questions_map_to_reports_scope(self) -> None:
        self.assertEqual(infer_amazon_scope("今天店铺卖了多少钱"), "reports")
        self.assertEqual(infer_amazon_scope("最近7天的销售额和销量"), "reports")


if __name__ == "__main__":
    unittest.main()
