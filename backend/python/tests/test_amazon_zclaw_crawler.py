from __future__ import annotations

import unittest
from unittest.mock import patch

from agent.amazon_chat_agent import read_live_amazon_data
from app.amazon.zclaw_crawler import _account_health_metrics, _content_text, _dashboard_metrics, crawl_zclaw_amazon


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


    @patch("app.amazon.zclaw_crawler.cli_tools.ziniao_page_visit")
    @patch("app.amazon.zclaw_crawler.cli_tools.ziniao_store_open")
    @patch("app.amazon.zclaw_crawler.cli_tools.ziniao_page_content")
    def test_crawl_uses_account_health_parser_for_account_health_scope(self, page_content, store_open, page_visit) -> None:
        store_open.return_value = {"ok": True}
        page_visit.return_value = {"ok": True}
        page_content.return_value = {"ok": True, "data": {"data": {"content": {"headings": ["账户状况评级 200"], "links": [{"text": "订单缺陷率 0%"}]}}}}
        result = crawl_zclaw_amazon(browser_id="store-1", store_name="Store", scope="account_health")
        self.assertEqual(result["metrics"][0]["metric_key"], "account_health_rating")
        self.assertEqual(result["result_summary"]["scope"], "account_health")

    @patch("app.amazon.zclaw_crawler.cli_tools.ziniao_page_visit")
    @patch("app.amazon.zclaw_crawler.cli_tools.ziniao_page_content")
    @patch("app.amazon.zclaw_crawler.cli_tools.ziniao_store_open")
    def test_crawl_navigates_to_scope_page_before_reading(self, store_open, page_content, page_visit) -> None:
        store_open.return_value = {"ok": True}
        page_visit.return_value = {"ok": True}
        page_content.return_value = {"ok": True, "data": {"data": {"content": {"headings": ["账户状况 良好"], "links": [{"text": "订单缺陷率 0%"}]}}}}
        crawl_zclaw_amazon(browser_id="store-1", store_name="Store", scope="account_health")
        page_visit.assert_called_once_with("store-1", "https://sellercentral.amazon.com/performance/account/health", wait_until="domcontentloaded")

    def test_dashboard_metrics_extracts_today_sales_and_orders_from_live_dashboard(self) -> None:
        text = "已订购商品销售额 US$9.99 已订购商品数量 1 转化率 -- 今天到目前为止"
        rows = {row["metric_key"]: row["value"] for row in _dashboard_metrics(text)}
        self.assertEqual(rows["today_sales"], "US$9.99")
        self.assertEqual(rows["today_orders"], "1")

    @patch("app.amazon.zclaw_crawler.time.sleep")
    @patch("app.amazon.zclaw_crawler.cli_tools.ziniao_page_visit")
    @patch("app.amazon.zclaw_crawler.cli_tools.ziniao_store_open")
    @patch("app.amazon.zclaw_crawler.cli_tools.ziniao_page_content")
    def test_crawl_retries_while_amazon_dashboard_is_still_loading(self, page_content, store_open, page_visit, sleep) -> None:
        store_open.return_value = {"ok": True}
        page_visit.return_value = {"ok": True}
        page_content.side_effect = [
            {"ok": True, "data": {"data": {"content": {"text": "正在加载..."}}}},
            {"ok": True, "data": {"data": {"content": {"text": "我的业务 今日全球销售额 US$10 未解决的订单 15 总余额 US$74 已订购商品销售额 US$9.99 已订购商品数量 1"}}}},
        ]
        result = crawl_zclaw_amazon(browser_id="store-1", store_name="Store", scope="daily")
        self.assertEqual(result["result_summary"]["transport"], "zclaw")
        self.assertEqual(result["result_summary"]["metrics_count"], 4)
        self.assertEqual(page_content.call_count, 2)
        sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
