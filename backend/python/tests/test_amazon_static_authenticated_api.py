from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app.amazon.static_authenticated_api import (
    StaticAuthenticatedEndpoint,
    StaticScopeResult,
    build_browser_fetch_script,
    fetch_static_scope,
)


def _daily_overview_mapper(body):
    if body.get("kind") != "overview":
        return {}
    return {"metrics": [{"metric_key": "today_sales", "value": "10", "status": "normal"}]}


def _daily_orders_mapper(body):
    if body.get("kind") != "orders":
        return {}
    return {"outbound_orders": [{"order_no": "123-1234567-1234567", "status": "pending"}]}


def _endpoint(*, key, provides, mapper, path="/internal/approved-api"):
    return StaticAuthenticatedEndpoint(
        key=key,
        scope="daily",
        page_url="https://sellercentral.amazon.com/home",
        method="GET",
        path=path,
        provides=frozenset(provides),
        version="v1",
        approved_at="2026-09-04",
        request_builder=lambda: {"query": {"day": "today"}},
        response_mapper=mapper,
    )


class AmazonStaticAuthenticatedApiTest(unittest.TestCase):
    def test_browser_script_uses_same_origin_session_without_cookie_export(self) -> None:
        endpoint = _endpoint(key="daily_overview_v1", provides={"metrics"}, mapper=_daily_overview_mapper)

        script = build_browser_fetch_script(endpoint)

        self.assertIn("credentials: 'same-origin'", script)
        self.assertIn('"path":"/internal/approved-api"', script)
        self.assertIn('"day":"today"', script)
        self.assertNotIn("document.cookie", script)
        self.assertNotIn("Authorization", script)

    def test_rejects_a_full_url_instead_of_a_same_origin_path(self) -> None:
        endpoint = _endpoint(
            key="daily_invalid_v1",
            provides={"metrics"},
            mapper=_daily_overview_mapper,
            path="https://example.invalid/internal/approved-api",
        )

        with self.assertRaisesRegex(ValueError, "same-origin"):
            build_browser_fetch_script(endpoint)

    @patch("app.amazon.static_authenticated_api.cli_tools.ziniao_page_exec")
    @patch("app.amazon.static_authenticated_api.cli_tools.ziniao_page_visit")
    def test_executes_only_registered_endpoints_and_merges_scope_data(self, page_visit, page_exec) -> None:
        overview = _endpoint(key="daily_overview_v1", provides={"metrics"}, mapper=_daily_overview_mapper)
        orders = _endpoint(key="daily_orders_v1", provides={"outbound_orders"}, mapper=_daily_orders_mapper)
        page_visit.return_value = {"ok": True}
        page_exec.side_effect = [
            {"ok": True, "data": json.dumps({"ok": True, "status": 200, "body": {"kind": "overview"}})},
            {"ok": True, "data": json.dumps({"ok": True, "status": 200, "body": {"kind": "orders"}})},
        ]

        with patch("app.amazon.static_authenticated_api.STATIC_AUTHENTICATED_ENDPOINTS", (overview, orders)):
            result = fetch_static_scope("store-1", "daily")

        self.assertTrue(result.complete)
        self.assertEqual(result.endpoint_keys, ["daily_overview_v1", "daily_orders_v1"])
        self.assertEqual(result.data["metrics"][0]["metric_key"], "today_sales")
        self.assertEqual(result.data["outbound_orders"][0]["order_no"], "123-1234567-1234567")
        page_visit.assert_called_once_with(
            "store-1",
            "https://sellercentral.amazon.com/home",
            wait_until="domcontentloaded",
            timeout=30,
        )
        self.assertEqual(page_exec.call_count, 2)

    @patch("app.amazon.static_authenticated_api.cli_tools.ziniao_page_exec")
    @patch("app.amazon.static_authenticated_api.cli_tools.ziniao_page_visit")
    def test_empty_registry_does_not_attempt_network_discovery(self, page_visit, page_exec) -> None:
        with patch("app.amazon.static_authenticated_api.STATIC_AUTHENTICATED_ENDPOINTS", ()):
            result = fetch_static_scope("store-1", "reports")

        self.assertFalse(result.complete)
        self.assertEqual(result.diagnostics, [])
        page_visit.assert_not_called()
        page_exec.assert_not_called()

    @patch("app.amazon.zclaw_crawler._visit_and_read")
    @patch("app.amazon.zclaw_crawler.fetch_static_scope")
    @patch("app.amazon.zclaw_crawler.cli_tools.ziniao_store_open")
    def test_complete_static_health_result_skips_page_fallback(self, store_open, fetch_scope, visit_and_read) -> None:
        store_open.return_value = {"ok": True}
        fetch_scope.return_value = StaticScopeResult(
            scope="account_health",
            data={
                "metrics": [{"metric_key": "order_defect_rate", "value": "0", "status": "normal"}],
                "products": [], "outbound_orders": [], "seller_news": [], "cases": [],
            },
            endpoint_keys=["account_health_v1"],
            endpoint_versions=["v1"],
            diagnostics=[{"endpoint_key": "account_health_v1", "status": "success"}],
            provided_fields={"metrics"},
        )

        from app.amazon.zclaw_crawler import crawl_zclaw_amazon

        result = crawl_zclaw_amazon(store_id="store-1", store_name="Store", scope="account_health")

        visit_and_read.assert_not_called()
        self.assertEqual(result["result_summary"]["transport"], "zclaw_api")
        self.assertFalse(result["result_summary"]["fallback_used"])


if __name__ == "__main__":
    unittest.main()
