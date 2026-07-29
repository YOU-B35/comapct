import unittest
from unittest.mock import MagicMock, patch

from app.crawler import competitor_discovery
from app.crawler.competitor_discovery import build_search_url, build_discovery_candidates


class CompetitorDiscoveryTest(unittest.TestCase):
    class _FakePage:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

        def is_closed(self):
            return self.closed

    class _FakeContext:
        def __init__(self):
            self.page = CompetitorDiscoveryTest._FakePage()

        def new_page(self):
            return self.page

    class _FakeRuntime:
        def __init__(self):
            self.context = CompetitorDiscoveryTest._FakeContext()

    def test_builds_za_search_url_with_encoded_keyword(self):
        self.assertEqual(
            build_search_url("fishing tackle", "za"),
            "https://www.temu.com/za/search_result.html?search_key=fishing%20tackle",
        )

    def test_groups_products_by_mall_id_in_search_order(self):
        search_url = build_search_url("fishing tackle", "za")
        items = [
            {
                "url": "https://www.temu.com/za/fishing-lure-g-601.html?mall_id=111&goods_id=601",
                "text": "Fishing Lure Set\n$5.99\n1.2K sold",
            },
            {
                "url": "https://www.temu.com/za/hooks-g-602.html?mall_id=111&goods_id=602",
                "text": "Fishing Hooks Kit\n$3.49\n500 sold",
            },
            {
                "url": "https://www.temu.com/za/fishing-line-g-603.html?mall_id=222&goods_id=603",
                "text": "Braided Fishing Line\n$7.25\n900 sold",
            },
        ]

        candidates = build_discovery_candidates(items, search_url=search_url, keyword="fishing tackle", limit=10)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["rank"], 1)
        self.assertEqual(candidates[0]["label"], "Fishing Lure Set")
        self.assertEqual(candidates[0]["url"], "https://www.temu.com/mall.html?mall_id=111")
        self.assertEqual(candidates[0]["sampleProductCount"], 2)
        self.assertTrue(candidates[0]["crawlable"])
        self.assertEqual(candidates[1]["rank"], 2)
        self.assertEqual(candidates[1]["url"], "https://www.temu.com/mall.html?mall_id=222")

    def test_falls_back_to_search_source_when_no_mall_id_is_available(self):
        search_url = build_search_url("fishing tackle", "za")
        items = [
            {
                "url": "https://www.temu.com/za/fishing-lure-g-601.html?goods_id=601",
                "text": "Fishing Lure Set\n$5.99\n1.2K sold",
            },
            {
                "url": "https://www.temu.com/za/fishing-hooks-g-602.html?goods_id=602",
                "text": "Fishing Hooks Kit\n$3.49\n500 sold",
            },
        ]

        candidates = build_discovery_candidates(items, search_url=search_url, keyword="fishing tackle", limit=10)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["label"], "fishing tackle 搜索结果候选源")
        self.assertEqual(candidates[0]["url"], search_url)
        self.assertEqual(candidates[0]["sampleProductCount"], 2)
        self.assertEqual(candidates[0]["sourceType"], "search")

    def test_retry_discovery_retries_profile_launch_after_forced_close(self):
        calls = []

        def fake_discover_raw_items(tenant_id, search_url, *, max_items):
            calls.append((tenant_id, search_url, max_items))
            if len(calls) == 1:
                raise RuntimeError("Target page, context or browser has been closed")
            return [{"url": "https://www.temu.com/mall.html?mall_id=1", "text": "Fishing lure\n$1.99\n10 sold"}]

        with patch.object(competitor_discovery, "discover_raw_items", side_effect=fake_discover_raw_items), \
                patch.object(competitor_discovery, "close_tenant_profile_browsers", return_value=1) as close_profiles, \
                patch.object(competitor_discovery.time, "sleep", return_value=None) as sleep:
            rows = competitor_discovery.retry_discovery_after_closing_profile(
                5,
                "https://www.temu.com/za/search_result.html?search_key=fishing",
                max_items=24,
                original=RuntimeError("initial profile failure"),
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(close_profiles.call_count, 2)
        self.assertEqual(sleep.call_count, 2)

    def test_retry_discovery_raises_profile_unavailable_after_final_launch_failure(self):
        with patch.object(
            competitor_discovery,
            "discover_raw_items",
            side_effect=RuntimeError("Target page, context or browser has been closed"),
        ), patch.object(competitor_discovery, "close_tenant_profile_browsers", return_value=1), \
                patch.object(competitor_discovery.time, "sleep", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "COMPETITOR_BROWSER_PROFILE_UNAVAILABLE"):
                competitor_discovery.retry_discovery_after_closing_profile(
                    5,
                    "https://www.temu.com/za/search_result.html?search_key=fishing",
                    max_items=24,
                    original=RuntimeError("initial profile failure"),
                )

    def test_discover_raw_items_reuses_live_browser_runtime(self):
        runtime = self._FakeRuntime()
        expected_rows = [{"url": "https://www.temu.com/mall.html?mall_id=1", "text": "Fishing lure\n$1.99\n10 sold"}]

        with patch("app.crawler.competitor_discovery.get_or_create_temu_runtime", return_value=runtime, create=True) as get_runtime, \
                patch.object(competitor_discovery, "extract_search_items_from_url", return_value=expected_rows) as extract_items, \
                patch.object(competitor_discovery, "close_tenant_profile_browsers", side_effect=AssertionError("should not close tenant profile during happy path")):
            rows = competitor_discovery.discover_raw_items(
                tenant_id=5,
                search_url="https://www.temu.com/za/search_result.html?search_key=fishing",
                max_items=24,
            )

        self.assertEqual(rows, expected_rows)
        get_runtime.assert_called_once()
        extract_items.assert_called_once_with(runtime.context.page, "https://www.temu.com/za/search_result.html?search_key=fishing", max_items=24)
        self.assertTrue(runtime.context.page.closed)

    def test_discover_raw_items_opens_manual_chrome_for_frontend_login(self):
        runtime = self._FakeRuntime()
        opened = {
            "tenant_id": 5,
            "opened": True,
            "engine": "manual_chrome",
            "url": "https://www.temu.com/za/search_result.html?search_key=fishing",
        }

        with patch("app.crawler.competitor_discovery.get_or_create_temu_runtime", return_value=runtime, create=True), \
                patch.object(
                    competitor_discovery,
                    "extract_search_items_from_url",
                    side_effect=RuntimeError("COMPETITOR_FRONTEND_LOGIN_REQUIRED: login required"),
                ), \
                patch.object(
                    competitor_discovery,
                    "open_manual_frontend_chrome",
                    return_value=opened,
                ) as open_chrome:
            with self.assertRaisesRegex(RuntimeError, "COMPETITOR_LOGIN_REQUIRED"):
                competitor_discovery.discover_raw_items(
                    tenant_id=5,
                    search_url="https://www.temu.com/za/search_result.html?search_key=fishing",
                    max_items=24,
                )

        self.assertTrue(runtime.context.page.closed)
        open_chrome.assert_called_once()

    def test_extract_search_items_retries_when_page_returns_no_rows(self):
        page = MagicMock()
        page.url = "https://www.temu.com/za/search_result.html?search_key=fishing"
        page.goto = MagicMock()
        page.wait_for_load_state = MagicMock()
        page.mouse = MagicMock()

        expected_rows = [{"url": "https://www.temu.com/mall.html?mall_id=1", "text": "Fishing lure\n$1.99\n10 sold"}]

        with patch.object(competitor_discovery, "human_pause", return_value=None), \
                patch.object(competitor_discovery, "ensure_discovery_page_accessible", return_value=None), \
                patch.object(
                    competitor_discovery,
                    "extract_search_items_from_page",
                    side_effect=[[], expected_rows],
                ) as extract_page, \
                patch.object(competitor_discovery, "is_temu_frontend_blocked", return_value=False):
            rows = competitor_discovery.extract_search_items_from_url(
                page,
                "https://www.temu.com/za/search_result.html?search_key=fishing",
                max_items=24,
            )

        self.assertEqual(rows, expected_rows)
        # initial attempt + retry attempt
        self.assertEqual(extract_page.call_count, 2)

    def test_extract_search_items_lenient_fallback_when_strict_empty(self):
        page = MagicMock()
        page.url = "https://www.temu.com/za/search_result.html?search_key=fishing"
        page.goto = MagicMock()
        page.wait_for_load_state = MagicMock()
        page.mouse = MagicMock()

        strict_rows = []
        expected_rows = [{"url": "https://www.temu.com/mall.html?mall_id=1", "text": "Fishing lure\nR281\n10 sold"}]

        with patch.object(competitor_discovery, "human_pause", return_value=None), \
                patch.object(competitor_discovery, "ensure_discovery_page_accessible", return_value=None), \
                patch.object(
                    competitor_discovery,
                    "extract_search_items_from_page",
                    return_value=strict_rows,
                ) as extract_strict, \
                patch.object(
                    competitor_discovery,
                    "extract_search_items_from_page_lenient",
                    return_value=expected_rows,
                ) as extract_lenient, \
                patch.object(competitor_discovery, "is_temu_frontend_blocked", return_value=False):
            rows = competitor_discovery.extract_search_items_from_url(
                page,
                "https://www.temu.com/za/search_result.html?search_key=fishing",
                max_items=24,
            )

        self.assertEqual(rows, expected_rows)
        extract_lenient.assert_called_once()
        # strict called multiple times: initial + 2 retries = 3
        self.assertEqual(extract_strict.call_count, 3)


if __name__ == "__main__":
    unittest.main()
