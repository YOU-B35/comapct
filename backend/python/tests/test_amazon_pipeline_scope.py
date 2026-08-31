"""采集编排策略回归测试：daily 也必须走 CSV 优先，DOM 兜底一律 fast。"""
from __future__ import annotations

from types import SimpleNamespace

from app.amazon import crawl_pipeline as cp


def test_daily_and_reports_use_csv_first() -> None:
    assert cp.scope_uses_csv("daily") is True
    assert cp.scope_uses_csv("reports") is True
    assert cp.scope_uses_csv("insights") is True
    assert cp.scope_uses_csv("account_health") is False


def test_orders_only_crawled_for_daily() -> None:
    assert cp.should_crawl_orders("daily") is True
    assert cp.should_crawl_orders("reports") is False
    assert cp.should_crawl_orders("account_health") is False


def test_br_dom_fallback_uses_fast_mode(monkeypatch) -> None:
    calls: dict[str, object] = {}
    page = SimpleNamespace(url="https://sellercentral.amazon.com/business-reports")

    def fake_csv(page, *, store_name):
        return SimpleNamespace(
            rows=[], page_url="", duration_ms=10, warning="ZERO_ROWS"
        )

    def fake_dom(page, *, store_name, fast):
        calls["fast"] = fast
        return []

    monkeypatch.setattr(cp, "crawl_business_report_csv", fake_csv)
    monkeypatch.setattr(cp, "crawl_business_report", fake_dom)
    monkeypatch.setattr(cp, "br_dom_fallback_enabled", lambda: True)

    rows, _key, _url, _ms, _warning = cp._load_business_report_products(
        page, store_name="x", use_csv=True
    )
    assert rows == []
    assert calls.get("fast") is True


def test_inventory_dom_fallback_uses_fast_mode(monkeypatch) -> None:
    calls: dict[str, object] = {}
    page = SimpleNamespace(url="https://sellercentral.amazon.com/inventory")

    def fake_csv(page, *, store_name):
        return SimpleNamespace(rows=[], page_url="", warning="ZERO_ROWS")

    def fake_dom(page, *, store_name, max_pages, fast):
        calls["fast"] = fast
        calls["max_pages"] = max_pages
        return []

    monkeypatch.setattr(cp, "crawl_inventory_csv", fake_csv)
    monkeypatch.setattr(cp, "crawl_inventory_products", fake_dom)
    monkeypatch.setattr(cp, "inventory_dom_fallback_enabled", lambda: True)

    rows, _key, _url, _warning = cp._load_inventory_products(
        page, store_name="x", use_csv=True
    )
    assert rows == []
    assert calls.get("fast") is True
    assert calls.get("max_pages") <= 2


def test_ads_dom_fallback_uses_fast_mode(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_csv(page, *, store_name, merchant_id, period_days):
        return SimpleNamespace(rows=[], merchant_id="", warning="ADS_CSV_EMPTY")

    def fake_dom(page, merchant_id, *, fast):
        calls["fast"] = fast
        return {}, [], "MOCK_MERCHANT"

    monkeypatch.setattr(cp, "crawl_ads_asin_csv", fake_csv)
    monkeypatch.setattr(cp, "crawl_ads_data", fake_dom)
    monkeypatch.setattr(cp, "ads_dom_fallback_enabled", lambda: True)

    campaigns, _summary, merchant, _key, _warning = cp._load_ads_campaigns(
        None, store_name="x", merchant_id="M1", use_csv=True
    )
    assert campaigns == []
    assert merchant == "MOCK_MERCHANT"
    assert calls.get("fast") is True
