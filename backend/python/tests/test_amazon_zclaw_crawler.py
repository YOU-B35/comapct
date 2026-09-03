from __future__ import annotations

import unittest
from unittest.mock import patch

from agent.amazon_chat_agent import read_live_amazon_data
from app.amazon.zclaw_crawler import _content_text, _dashboard_metrics


class ZclawAmazonCrawlerTest(unittest.TestCase):
    def test_content_text_extracts_nested_structured_body(self) -> None:
        raw = {"data": {"data": {"content": {"bodyText": "未解决的订单 16 总余额 US$72"}}}}
        self.assertEqual(_content_text(raw), "未解决的订单 16 总余额 US$72")

    def test_dashboard_metrics_extracts_known_values(self) -> None:
        text = "未解决的订单 16 总余额 US$72 最近 7 天 带来的销售额 US$9.99 支出 US$58.62 广告支出回报 0.17"
        rows = {row["metric_key"]: row["value"] for row in _dashboard_metrics(text)}
        self.assertEqual(rows["unresolved_orders"], "16")
        self.assertEqual(rows["total_balance"], "US$72")
        self.assertEqual(rows["ad_sales_7d"], "US$9.99")
        self.assertEqual(rows["ad_spend_7d"], "US$58.62")

    def test_live_reader_prefers_zclaw_for_bound_store(self) -> None:
        crawled = {"metrics": [{"metric_key": "balance", "label": "balance", "value": "US$72", "status": "normal"}], "result_summary": {"metrics_count": 1, "transport": "zclaw"}}
        with patch("agent.amazon_chat_agent.crawl_zclaw_amazon", return_value=crawled) as zclaw, patch("agent.amazon_chat_agent.crawl_amazon") as webdriver:
            result = read_live_amazon_data(question="当前销售额", store_name="Store", payload={"browser_id": "store-1", "platform_account_id": "p1"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["source"]["type"], "ziniao_zclaw")
        self.assertEqual(result["source"]["name"], "ziniao_zclaw:reports")
        zclaw.assert_called_once()
        webdriver.assert_not_called()

    def test_live_reader_falls_back_to_webdriver_after_zclaw_failure(self) -> None:
        crawled = {"metrics": [], "result_summary": {"products_count": 0, "orders_count": 0}}
        with patch("agent.amazon_chat_agent.crawl_zclaw_amazon", side_effect=RuntimeError("bridge unavailable")), patch("agent.amazon_chat_agent.crawl_amazon", return_value=crawled) as webdriver:
            result = read_live_amazon_data(question="当前账户健康", store_name="Store", payload={"browser_id": "store-1", "platform_account_id": "p1"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["source"]["type"], "ziniao_webdriver")
        webdriver.assert_called_once()


if __name__ == "__main__":
    unittest.main()
