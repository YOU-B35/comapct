import unittest
from unittest.mock import MagicMock, patch

from agent.handlers import handle_amazon_sync, handle_amazon_write
from app.observability.task_timing import finish_task_timing, record_duration, start_task_timing


class AmazonTaskTimingContextTests(unittest.TestCase):
    def test_sync_nested_worker_contributes_to_task_timing(self):
        timing, token = start_task_timing("amazon_sync", "amazon-sync-1")
        client = MagicMock()
        task = {
            "task_id": "amazon-sync-1",
            "payload": {"scope": "daily", "browser_id": "browser-1"},
        }

        def crawl(**_kwargs):
            record_duration("amazon_home.open", 0.25)
            return {"result_summary": {}}

        with patch("agent.handlers.crawl_amazon", side_effect=crawl):
            handle_amazon_sync(client, task)

        payload = finish_task_timing(timing, token, outcome="handled")
        self.assertEqual(payload["stages_ms"]["amazon_home.open"], 250)

    def test_account_health_sync_uses_zclaw_without_starting_webdriver(self):
        client = MagicMock()
        task = {
            "task_id": "amazon-sync-zclaw-1",
            "payload": {"scope": "account_health", "store_name": "Store"},
        }
        zclaw_result = {"metrics": [{"metric_key": "account_health_status", "value": "良好"}], "result_summary": {"transport": "zclaw", "complete": True}}

        with patch("agent.handlers.crawl_zclaw_amazon", return_value=zclaw_result) as zclaw, patch("agent.handlers.crawl_amazon") as webdriver:
            handle_amazon_sync(client, task)

        zclaw.assert_called_once_with(store_id="", store_name="Store", scope="account_health")
        webdriver.assert_not_called()
        client.complete_task_with_retry.assert_called_once_with("amazon-sync-zclaw-1", status="success", result=zclaw_result)

    def test_sync_reports_actionable_error_when_ziniao_is_in_normal_mode(self):
        client = MagicMock()
        task = {
            "task_id": "amazon-sync-normal-mode-1",
            "payload": {"scope": "daily", "browser_id": "browser-1", "store_name": "Store"},
        }

        with patch("agent.handlers.crawl_zclaw_amazon", side_effect=RuntimeError("CLI store is unavailable")), patch(
            "agent.handlers.crawl_amazon", side_effect=RuntimeError("检测到紫鸟正在普通模式运行（无 WebDriver API）")
        ):
            handle_amazon_sync(client, task)

        client.complete_task_with_retry.assert_called_once()
        _, kwargs = client.complete_task_with_retry.call_args
        self.assertEqual(kwargs["error_code"], "AMAZON_WEBDRIVER_MODE_REQUIRED")
        self.assertIn("WebDriver 开发者模式", kwargs["error_message"])

    def test_cli_bound_daily_sync_does_not_fall_back_to_webdriver(self):
        client = MagicMock()
        task = {
            "task_id": "amazon-sync-cli-daily-1",
            "payload": {"scope": "daily", "ziniao_store_id": "cli-store-1", "store_name": "Store"},
        }
        zclaw_result = {"outbound_orders": [{"order_no": "123-1234567-1234567"}], "result_summary": {"transport": "zclaw", "complete": True}}

        with patch("agent.handlers.crawl_zclaw_amazon", return_value=zclaw_result) as zclaw, patch("agent.handlers.crawl_amazon") as webdriver:
            handle_amazon_sync(client, task)

        zclaw.assert_called_once_with(store_id="cli-store-1", store_name="Store", scope="daily")
        webdriver.assert_not_called()

    def test_normal_mode_surfaces_cli_authorization_requirement(self):
        client = MagicMock()
        task = {
            "task_id": "amazon-sync-cli-config-1",
            "payload": {"scope": "daily", "browser_id": "browser-1", "store_name": "Store"},
        }

        with patch("agent.handlers.crawl_zclaw_amazon", side_effect=RuntimeError("找不到配置文件，请执行 ziniao-cli config init")), patch(
            "agent.handlers.crawl_amazon", side_effect=RuntimeError("检测到紫鸟正在普通模式运行（无 WebDriver API）")
        ):
            handle_amazon_sync(client, task)

        _, kwargs = client.complete_task_with_retry.call_args
        self.assertEqual(kwargs["error_code"], "AMAZON_ZINIAO_CLI_SETUP_REQUIRED")
        self.assertIn("无需配置 ZINIAO_CLI_BIN", kwargs["error_message"])

    def test_write_nested_worker_contributes_to_task_timing(self):
        timing, token = start_task_timing("amazon_write", "amazon-write-1")
        client = MagicMock()
        task = {
            "task_id": "amazon-write-1",
            "payload": {"action": "update_price", "browser_id": "browser-1"},
        }

        def write(**_kwargs):
            record_duration("amazon_write.request", 0.1)
            return {"ok": True}

        with patch("agent.handlers.execute_amazon_write", side_effect=write):
            handle_amazon_write(client, task)

        payload = finish_task_timing(timing, token, outcome="handled")
        self.assertEqual(payload["stages_ms"]["amazon_write.request"], 100)


if __name__ == "__main__":
    unittest.main()
