import unittest
from unittest.mock import MagicMock, patch

from app.crawler import temu_crawler


class LiveCrawlLoginWaitTests(unittest.TestCase):
    def test_live_crawl_waits_for_login_before_calling_api_client(self):
        context_manager = MagicMock()
        browser_context = MagicMock()
        page = MagicMock()
        context_manager.__enter__.return_value = (MagicMock(), browser_context)
        context_manager.__exit__.return_value = None

        client = MagicMock()
        client.get_shop_info.return_value = ("Shop A", "mall-123")
        client.fetch_all_sales.return_value = []

        with patch.object(temu_crawler, "read_ready_session_cache", return_value=None), \
                patch("app.browser.temu_cookie_trust.temu_login_cookies_alive", return_value=False), \
                patch.object(temu_crawler, "ensure_profile_available"), \
                patch.object(temu_crawler, "close_tenant_profile_browsers"), \
                patch.object(temu_crawler, "open_temu_context", return_value=context_manager) as open_ctx, \
                patch.object(temu_crawler, "get_or_open_seller_page", return_value=page), \
                patch.object(temu_crawler, "wait_for_login_and_mall", return_value="mall-123") as wait, \
                patch.object(temu_crawler, "_resolve_malls", return_value=[{"mallId": "mall-123", "mallName": "Shop A"}]), \
                patch.object(temu_crawler, "TemuApiClient", return_value=client), \
                patch.object(temu_crawler, "describe_session", return_value={"url": "https://agentseller.temu.com/", "logged_in": True}), \
                patch.object(temu_crawler, "write_session_cache"):
            result = temu_crawler.crawl_temu_sales_live("2026-07-06", tenant_id=5)

        wait.assert_called_once()
        self.assertEqual(wait.call_args.kwargs.get("tenant_id"), 5)
        self.assertEqual(result["shops"][0]["shop_id"], "mall-123")
        open_ctx.assert_called_once()
        self.assertTrue(open_ctx.call_args.kwargs.get("skip_profile_pull") is True)
        client.get_shop_info.assert_not_called()

    def test_live_crawl_uses_cookies_without_wait_when_alive(self):
        context_manager = MagicMock()
        browser_context = MagicMock()
        page = MagicMock()
        context_manager.__enter__.return_value = (MagicMock(), browser_context)
        context_manager.__exit__.return_value = None

        client = MagicMock()
        client.get_shop_info.return_value = ("Shop A", "mall-123")
        client.fetch_all_sales.return_value = []

        with patch.object(temu_crawler, "read_ready_session_cache", return_value=None), \
                patch("app.browser.temu_cookie_trust.temu_login_cookies_alive", return_value=True), \
                patch.object(temu_crawler, "ensure_profile_available"), \
                patch.object(temu_crawler, "close_tenant_profile_browsers"), \
                patch.object(temu_crawler, "open_temu_context", return_value=context_manager), \
                patch.object(temu_crawler, "get_or_open_seller_page", return_value=page), \
                patch.object(temu_crawler, "ensure_logged_in", return_value="mall-123") as ensure, \
                patch.object(temu_crawler, "wait_for_login_and_mall") as wait, \
                patch.object(temu_crawler, "_resolve_malls", return_value=[{"mallId": "mall-123", "mallName": "Shop A"}]), \
                patch.object(temu_crawler, "TemuApiClient", return_value=client), \
                patch.object(temu_crawler, "describe_session", return_value={"url": "https://agentseller.temu.com/", "logged_in": True}), \
                patch.object(temu_crawler, "write_session_cache"):
            result = temu_crawler.crawl_temu_sales_live(
                "2026-07-06", tenant_id=5, session_key="18061740604"
            )

        ensure.assert_called_once()
        wait.assert_not_called()
        self.assertEqual(result["shops"][0]["shop_id"], "mall-123")
        client.get_shop_info.assert_not_called()

    def test_live_crawl_falls_back_to_shop_info_when_mall_name_missing(self):
        context_manager = MagicMock()
        browser_context = MagicMock()
        page = MagicMock()
        context_manager.__enter__.return_value = (MagicMock(), browser_context)
        context_manager.__exit__.return_value = None

        client = MagicMock()
        client.get_shop_info.return_value = ("Resolved shop", "mall-123")
        client.fetch_all_sales.return_value = []

        with patch.object(temu_crawler, "read_ready_session_cache", return_value=None), \
                patch("app.browser.temu_cookie_trust.temu_login_cookies_alive", return_value=True), \
                patch.object(temu_crawler, "ensure_profile_available"), \
                patch.object(temu_crawler, "close_tenant_profile_browsers"), \
                patch.object(temu_crawler, "open_temu_context", return_value=context_manager), \
                patch.object(temu_crawler, "get_or_open_seller_page", return_value=page), \
                patch.object(temu_crawler, "ensure_logged_in", return_value="mall-123"), \
                patch.object(temu_crawler, "_resolve_malls", return_value=[{"mallId": "mall-123", "mallName": ""}]), \
                patch.object(temu_crawler, "TemuApiClient", return_value=client), \
                patch.object(temu_crawler, "describe_session", return_value={"url": "https://agentseller.temu.com/", "logged_in": True}), \
                patch.object(temu_crawler, "write_session_cache"):
            result = temu_crawler.crawl_temu_sales_live("2026-07-06", tenant_id=5)

        client.get_shop_info.assert_called_once()
        self.assertEqual(result["shops"][0]["shop_name"], "Resolved shop")


if __name__ == "__main__":
    unittest.main()
