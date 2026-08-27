"""Regression tests for PDD live XHR sync flow and field mapping."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any


class _FakeClient:
    def __init__(self) -> None:
        self.account_payload: dict[str, Any] = {}
        self.ingest: list[tuple[str, dict[str, Any]]] = []

    def list_platform_accounts(self, tenant_id: int) -> dict[str, Any]:
        return self.account_payload

    def _record(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.ingest.append((name, payload))
        return {"ok": True, "name": name}

    def ingest_pdd_orders(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._record("orders", payload)

    def ingest_pdd_products(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._record("products", payload)

    def ingest_pdd_compass(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._record("compass", payload)

    def ingest_pdd_issues(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._record("issues", payload)


def _task(tenant_id: int, store_id: str, job_id: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "tenant_id": tenant_id,
        "store_id": store_id,
        "job_id": job_id,
        **extra,
    }
    return {"payload": payload}


def _pdd_order_row(
    *,
    order_sn: str = "202608261234567890",
    create_time: Any = "2026-08-26 10:30:00",
    goods: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "order_sn": order_sn,
        "order_status": 3,
        "order_status_text": "已发货",
        "order_amount": 12800,
        "pay_amount": 12800,
        "receiver_name": "张**",
        "create_time": create_time,
        "pay_time": create_time,
        "mall_id": "mall-1001",
        "goods_list": goods
        or [
            {
                "goods_name": "测试商品A",
                "spec": "红色/M",
                "goods_num": 2,
                "goods_price": 4900,
                "goods_amount": 9800,
                "goods_img": "https://img.example.com/a.jpg",
            },
            {
                "goods_name": "测试商品B",
                "spec": "蓝色/L",
                "goods_num": 1,
                "goods_price": 3000,
                "goods_amount": 3000,
            },
        ],
    }


def test_mock_mode_disabled_and_live_ready() -> None:
    from agent import pdd_tasks as mod

    assert mod._MOCK_ORDERS_ENABLED is False
    assert mod._MOCK_PRODUCTS_ENABLED is False
    assert mod._MOCK_COMPASS_ENABLED is False
    assert mod._MOCK_ISSUES_ENABLED is False
    assert mod.PDD_ORDERS_XHR_READY is True
    assert mod.PDD_PRODUCTS_XHR_READY is True


def test_pdd_profile_root_defaults_to_repo_in_dev() -> None:
    from agent import pdd_tasks as mod

    assert mod._pdd_profile_root() == mod.ROOT


def test_profile_dir_separates_stores_for_multi_account(monkeypatch: Any) -> None:
    from agent import pdd_tasks as mod

    root = Path(tempfile.mkdtemp())
    monkeypatch.setattr(mod, "_pdd_profile_root", lambda: root)
    p1 = mod.profile_dir(5, None)
    p_default = mod.profile_dir(5, "default")
    p2 = mod.profile_dir(5, "fdc163b5-e485-4a49-8201-cbc6af8ac72c")
    flat = root / ".pdd-browser-profile" / "tenant-5"
    assert p1 == flat
    assert p_default == flat
    assert p2 == root / ".pdd-browser-profile" / "tenant-5" / "account-fdc163b5-e485-4a49-8201-cbc6af8ac72c"


def test_resolve_store_id_defaults_when_empty() -> None:
    from agent.pdd_tasks import _resolve_store_id

    class _Client:
        def list_platform_accounts(self, tenant_id: int) -> dict[str, Any]:
            return {"pdd": [{"id": "fdc163b5"}]}

    assert _resolve_store_id(_Client(), 5, "") == "fdc163b5"
    assert _resolve_store_id(_Client(), 5, "fdc163b5") == "fdc163b5"
    assert _resolve_store_id(_Client(), 5, "bbb") == "bbb"


def test_resolve_store_id_falls_back_to_default_without_accounts() -> None:
    from agent.pdd_tasks import _resolve_store_id

    class _NoAccounts:
        def list_platform_accounts(self, tenant_id: int) -> dict[str, Any]:
            return {"pdd": []}

    assert _resolve_store_id(_NoAccounts(), 5, "") == "default"


def test_resolve_profile_store_id_default_store_uses_flat_profile() -> None:
    from agent.pdd_tasks import _default_pdd_store_id, _resolve_profile_store_id

    class _Client:
        def list_platform_accounts(self, tenant_id: int) -> dict[str, Any]:
            # 列表按绑定时间倒序：最后一项为最早绑定（默认店铺）
            return {"pdd": [{"id": "newest"}, {"id": "fdc163b5"}]}

    assert _default_pdd_store_id(_Client(), 5) == "fdc163b5"
    assert _resolve_profile_store_id(_Client(), 5, "") == "default"
    assert _resolve_profile_store_id(_Client(), 5, "fdc163b5") == "default"
    assert _resolve_profile_store_id(_Client(), 5, "second-store") == "second-store"


def test_row_looks_like_order_accepts_pdd_payload() -> None:
    from agent.pdd_tasks import _row_looks_like_order

    assert _row_looks_like_order(_pdd_order_row()) is True
    assert _row_looks_like_order({"foo": "bar"}) is False


def test_find_list_rows_extracts_nested_order_list() -> None:
    from agent.pdd_tasks import _find_list_rows

    payload = {
        "success": True,
        "errorCode": 10000,
        "result": {
            "orderList": [_pdd_order_row(order_sn="A"), _pdd_order_row(order_sn="B")],
            "total": 2,
        },
    }
    rows = _find_list_rows(payload, "orders")
    assert rows is not None
    assert len(rows) == 2


def test_map_order_row_maps_all_fields_and_converts_fen() -> None:
    from agent.pdd_tasks import _map_order_row

    row = _map_order_row(_pdd_order_row())
    assert row["order_no"] == "202608261234567890"
    assert row["order_key"] == "pdd:202608261234567890"
    assert row["external_shop_id"] == "mall-1001"
    assert row["product_name"] == "测试商品A / 测试商品B"
    assert row["sku_text"] == "红色/M / 蓝色/L"
    assert row["quantity"] == 3
    assert row["paid_amount"] == "128.00"
    assert row["amount"] == "128.00"
    assert row["item_amount"] == "128.00"
    assert row["unit_price"] == "39.50"
    assert row["currency"] == "CNY"
    assert row["status"] == "已发货"
    assert row["ordered_at"] == "2026-08-26 10:30:00"
    assert row["paid_at"] == "2026-08-26 10:30:00"
    assert row["buyer_masked"] == "张**"
    assert row["image_url"] == "https://img.example.com/a.jpg"
    assert row["report_day"] == "2026-08-26"


def test_map_order_row_flat_recent_order_list() -> None:
    from agent.pdd_tasks import _map_order_row

    raw = {
        "order_sn": "260826-123456789012345",
        "order_status": 1,
        "order_status_str": "待发货",
        "order_time": 1787682600,
        "goods_name": "YOTO钓组配件",
        "spec": "4#【转环QC型】,60个装",
        "goods_number": 2,
        "goods_price": 1520,
        "goods_amount": 3040,
        "order_amount": 3040,
        "receive_name": "谢***",
        "thumb_url": "https://img.pddpic.com/x.jpg",
    }
    row = _map_order_row(raw)
    assert row["order_no"] == "260826-123456789012345"
    assert row["product_name"] == "YOTO钓组配件"
    assert row["sku_text"] == "4#【转环QC型】,60个装"
    assert row["quantity"] == 2
    assert row["paid_amount"] == "30.40"
    assert row["item_amount"] == "30.40"
    assert row["unit_price"] == "15.20"
    assert row["status"] == "待发货"
    assert row["ordered_at"].startswith("2026-08-26")
    assert row["buyer_masked"] == "谢***"
    assert row["image_url"] == "https://img.pddpic.com/x.jpg"
    assert row["report_day"] == "2026-08-26"


def test_map_order_row_unpaid_has_zero_paid_amount() -> None:
    from agent.pdd_tasks import _map_order_row

    raw = {
        "order_sn": "260827-UNPAID000000001",
        "order_status": 0,
        "order_status_str": "待付款",
        "pay_status": 0,
        "pay_time": 0,
        "order_time": 1787788800,
        "order_amount": 1650,
        "goods_name": "测试商品",
        "goods_number": 1,
        "goods_price": 1650,
        "goods_amount": 1650,
    }
    row = _map_order_row(raw)
    assert row["paid_amount"] == "0"
    assert row["paid_at"] == ""
    assert row["amount"] == "16.50"


def test_row_looks_like_product_rejects_ad_strategy_and_accepts_goods() -> None:
    from agent.pdd_tasks import _row_looks_like_product

    ad_row = {
        "goodsId": 993978449219,
        "title": "去推广",
        "tagText": "去推广",
        "buttonText": "去推广",
        "jumpUrl": "https://yingxiao.pinduoduo.com/cube/flow",
    }
    goods_row = {
        "id": 993978449219,
        "goods_name": "YOTO钓组配件",
        "sku_price": [2080, 2400],
        "quantity": 800,
        "thumb_url": "https://img.pddpic.com/x.jpg",
    }
    assert _row_looks_like_product(ad_row) is False
    assert _row_looks_like_product(goods_row) is True


def test_map_product_row_real_goods_list() -> None:
    from agent.pdd_tasks import _map_product_row

    raw = {
        "id": 993978449219,
        "goods_name": "YOTO钓组配件",
        "sku_group_price": [1950, 2290],
        "sku_price": [2080, 2400],
        "quantity": 800,
        "sold_quantity_for_thirty_days": 12,
        "thumb_url": "https://img.pddpic.com/x.jpg",
        "cat_name_1": "户外",
        "cat_name_2": "钓具",
        "out_goods_sn": "ABC123",
        "sku_list": [{"spec": "红色"}],
        "is_onsale": True,
    }
    row = _map_product_row(raw)
    assert row["product_id"] == "993978449219"
    assert row["product_name"] == "YOTO钓组配件"
    assert row["price"] == "19.50"
    assert row["stock"] == 800
    assert row["sales"] == 12
    assert row["category"] == "户外 / 钓具"
    assert row["article_no"] == "ABC123"
    assert row["status"] == "在售"
    assert row["sku_count"] == 1


def test_format_pdd_time_handles_unix_millis() -> None:
    from datetime import datetime, timezone, timedelta

    from agent.pdd_tasks import _format_pdd_time

    expected = datetime(2026, 8, 26, 10, 30, 0, tzinfo=timezone(timedelta(hours=8))).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    millis = int(datetime(2026, 8, 26, 2, 30, 0, tzinfo=timezone.utc).timestamp() * 1000)
    assert _format_pdd_time(millis) == expected
    assert _format_pdd_time("2026-08-26 10:30:00") == "2026-08-26 10:30:00"
    assert _format_pdd_time("") == ""


def test_sanitize_utf8_removes_lone_surrogates() -> None:
    from agent.pdd_tasks import _sanitize_utf8

    payload = {
        "order_no": "A",
        "raw_json": "emoji \ud83d broken",
        "nested": [{"name": "ok \ud83d\ude00"}, 1, None],
    }
    out = _sanitize_utf8(payload)
    assert "\ud83d" not in out["raw_json"]
    assert all(0xD800 <= ord(ch) <= 0xDFFF for ch in out["nested"][0]["name"]) is False
    assert out["nested"][1] == 1
    assert out["nested"][2] is None


def test_set_page_in_payload_updates_page_num() -> None:
    from agent.pdd_tasks import _set_page_in_payload

    payload = {"pageNum": 1, "pageSize": 10, "antiContent": "abc"}
    out = _set_page_in_payload(payload, 2, 100)
    assert out["pageNum"] == 2
    assert out["pageSize"] == 100
    assert out["antiContent"] == "abc"


def test_set_page_in_url_updates_page_param() -> None:
    from agent.pdd_tasks import _set_page_in_url

    url = _set_page_in_url(
        "https://mms.pinduoduo.com/order/queryOrderList?page=1&size=10",
        3,
        50,
    )
    assert "page=3" in url
    assert "size=50" in url


def _fake_launch(monkeypatch: Any, orders_rows: list[dict[str, Any]], products_rows: list[dict[str, Any]]) -> None:
    from agent import pdd_tasks as mod

    class _FakeContext:
        def close(self) -> None:
            pass

    class _FakePw:
        def stop(self) -> None:
            pass

    class _FakePage:
        pass

    def launch(*args: Any, **kwargs: Any) -> tuple[Any, Any, Any]:
        return _FakePw(), _FakeContext(), _FakePage()

    def looks_logged_in(page, context=None) -> bool:
        return True

    def fetch_orders(page, **kwargs: Any) -> tuple[list[dict[str, Any]], str]:
        return orders_rows, "https://mms.pinduoduo.com/order/queryOrderList"

    def fetch_products(page, **kwargs: Any) -> tuple[list[dict[str, Any]], str]:
        return products_rows, "https://mms.pinduoduo.com/goods/goodsList"

    monkeypatch.setattr(mod, "_launch", launch)
    monkeypatch.setattr(mod, "_looks_logged_in", looks_logged_in)
    monkeypatch.setattr(mod, "fetch_orders_via_xhr", fetch_orders)
    monkeypatch.setattr(mod, "fetch_products_via_xhr", fetch_products)


def test_orders_sync_launches_browser_and_groups_by_day(monkeypatch: Any) -> None:
    from agent.pdd_tasks import run_orders_sync

    orders = [
        _map_order(_pdd_order_row(order_sn="D1-1"), "2026-08-25"),
        _map_order(_pdd_order_row(order_sn="D2-1"), "2026-08-26"),
    ]
    _fake_launch(monkeypatch, orders, [])
    client = _FakeClient()
    result = run_orders_sync(
        client,
        _task(7, "shop-orders-4", "job-orders-4", date_window="d7"),
    )
    assert result.get("scope") == "orders"
    assert result.get("orders_count") == 2
    name, body = client.ingest[-1]
    assert name == "orders"
    assert body["store_id"] == "shop-orders-4"
    assert body["date_window"] == "d30"
    days = body["days"]
    assert len(days) == 2
    by_day = {d["replace_day"]: d["orders"] for d in days}
    assert len(by_day["2026-08-25"]) == 1
    assert len(by_day["2026-08-26"]) == 1


def _map_order(raw: dict[str, Any], report_day: str) -> dict[str, Any]:
    from agent.pdd_tasks import _map_order_row

    row = _map_order_row(raw)
    row["report_day"] = report_day
    return row


def test_products_sync_launches_browser_and_ingests(monkeypatch: Any) -> None:
    from agent.pdd_tasks import run_products_sync

    products = [
        {
            "product_id": "G1001",
            "product_name": "测试商品",
            "price": "99.00",
            "stock": 10,
        }
    ]
    _fake_launch(monkeypatch, [], products)
    client = _FakeClient()
    result = run_products_sync(
        client,
        _task(8, "shop-products-5", "job-products-5"),
    )
    assert result.get("scope") == "products"
    name, body = client.ingest[-1]
    assert name == "products"
    assert body["store_id"] == "shop-products-5"
    assert body["products"] == products


def test_fetch_orders_without_page_raises_live_error() -> None:
    from agent.pdd_tasks import fetch_orders_via_xhr

    try:
        fetch_orders_via_xhr(page=None, date_window="today", store_id="s1")
    except RuntimeError as exc:
        assert "PDD_ORDERS_SOURCE_UNAVAILABLE" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError when page is None")


def test_fetch_products_without_page_raises_live_error() -> None:
    from agent.pdd_tasks import fetch_products_via_xhr

    try:
        fetch_products_via_xhr(page=None, store_id="s1")
    except RuntimeError as exc:
        assert "PDD_PRODUCTS_SOURCE_UNAVAILABLE" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError when page is None")


def test_pdd_seller_home_is_dashboard_not_login() -> None:
    from app.browser.pdd_context import PDD_SELLER_HOME, is_pdd_auth_url

    assert "/login" not in PDD_SELLER_HOME.lower()
    assert is_pdd_auth_url("https://mms.pinduoduo.com/login/") is True
    assert is_pdd_auth_url("https://mms.pinduoduo.com/") is False


def test_pdd_launch_kwargs_uses_bundled_chromium(monkeypatch: Any) -> None:
    from agent import pdd_tasks as mod

    monkeypatch.setattr("app.browser.context._bundled_chromium_ready", lambda: True)
    monkeypatch.setattr("app.config.BROWSER_CHANNEL", None)
    kwargs = mod._pdd_launch_kwargs(headless=True)
    assert "channel" not in kwargs
    assert "executable_path" not in kwargs


def test_pdd_launch_kwargs_rejects_system_chrome_fallback(monkeypatch: Any) -> None:
    from agent import pdd_tasks as mod

    monkeypatch.setattr("app.browser.context._bundled_chromium_ready", lambda: False)
    monkeypatch.setattr("app.config.BROWSER_CHANNEL", None)
    try:
        mod._pdd_launch_kwargs(headless=True)
    except RuntimeError as exc:
        assert "PDD_BROWSER_UNAVAILABLE" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError when bundled Chromium is missing")


def test_resolve_sync_store_ids_returns_all_accounts() -> None:
    from agent.pdd_tasks import _resolve_sync_store_ids

    class _Client:
        def list_platform_accounts(self, tenant_id: int) -> dict[str, Any]:
            return {"pdd": [{"id": "store-a"}, {"id": "store-b"}]}

    assert _resolve_sync_store_ids(_Client(), 5, "") == ["store-a", "store-b"]
    assert _resolve_sync_store_ids(_Client(), 5, "store-b") == ["store-b"]


def test_orders_sync_all_stores_ingests_logged_in_and_skips_others(monkeypatch: Any) -> None:
    from agent import pdd_tasks as mod

    class _FakeContext:
        def close(self) -> None:
            pass

    class _FakePw:
        def stop(self) -> None:
            pass

    class _FakePage:
        pass

    profile_logged_in = {"store-a": True, "store-b": False, "default": True}

    def launch(*args: Any, **kwargs: Any) -> tuple[Any, Any, Any]:
        page = _FakePage()
        page.store_id = kwargs.get("store_id") or "default"
        return _FakePw(), _FakeContext(), page

    def looks_logged_in(page, context=None) -> bool:
        return profile_logged_in.get(getattr(page, "store_id", ""), False)

    def fetch_orders(page, **kwargs: Any) -> tuple[list[dict[str, Any]], str]:
        sid = str(kwargs.get("store_id") or "default")
        return [_map_order(_pdd_order_row(order_sn="O-" + sid), "2026-08-26")], (
            "https://mms.pinduoduo.com/order/queryOrderList"
        )

    monkeypatch.setattr(mod, "_launch", launch)
    monkeypatch.setattr(mod, "_looks_logged_in", looks_logged_in)
    monkeypatch.setattr(mod, "fetch_orders_via_xhr", fetch_orders)

    client = _FakeClient()
    client.account_payload = {"pdd": [{"id": "store-a"}, {"id": "store-b"}, {"id": "store-c"}]}
    result = mod.run_orders_sync(client, _task(7, "", "job-all-orders"))

    assert result["orders_count"] == 2
    assert result["partial"] is True
    ingested_stores = [body["store_id"] for name, body in client.ingest if name == "orders"]
    assert ingested_stores == ["store-a", "store-c"]


def test_looks_kind_api_url_rejects_recent_order_widget() -> None:
    from agent.pdd_tasks import _looks_kind_api_url

    assert _looks_kind_api_url(
        "https://mms.pinduoduo.com/mangkhut/mms/recentOrderList", "orders"
    ) is True
    assert _looks_kind_api_url(
        "https://mms.pinduoduo.com/mars/shop/mergeShipping/newOrderList", "orders"
    ) is False
    assert _looks_kind_api_url(
        "https://mms.pinduoduo.com/mangkhut/mms/order/queryOrderList", "orders"
    ) is True


def test_find_list_rows_extracts_result_page_items() -> None:
    from agent.pdd_tasks import _find_list_rows

    payload = {
        "success": True,
        "errorCode": 10000,
        "result": {
            "totalItemNum": 2,
            "pageItems": [_pdd_order_row(order_sn="P1"), _pdd_order_row(order_sn="P2")],
        },
    }
    rows = _find_list_rows(payload, "orders")
    assert rows is not None
    assert [r["order_sn"] for r in rows] == ["P1", "P2"]


def test_extract_total_count_reads_nested_total_item_num() -> None:
    from agent.pdd_tasks import _extract_total_count

    payload = {
        "result": {
            "totalItemNum": 8237,
            "pageItems": [{"order_sn": "x"}],
        }
    }
    assert _extract_total_count(payload, 1) == 8237
    assert _extract_total_count({"total": 5}, 1) == 5
    assert _extract_total_count({"foo": "bar"}, 3) == 3


def test_set_page_in_payload_preserves_group_window() -> None:
    from agent.pdd_tasks import _set_page_in_payload

    payload = {
        "orderType": 0,
        "groupStartTime": 1780033080,
        "groupEndTime": 1787809080,
        "pageNumber": 1,
        "pageSize": 20,
        "sortType": 10,
    }
    out = _set_page_in_payload(payload, 2, 50)
    assert out["pageNumber"] == 2
    assert out["pageSize"] == 50
    assert out["groupStartTime"] == 1780033080
    assert out["groupEndTime"] == 1787809080
    assert out["orderType"] == 0


def test_normalize_orders_post_data_forces_all_orders() -> None:
    from agent.pdd_tasks import _normalize_orders_post_data

    post = (
        '{"orderType":1,"afterSaleType":1,"remarkStatus":-1,"urgeShippingStatus":-1,'
        '"groupStartTime":1780033080,"groupEndTime":1787809080,"pageNumber":1,'
        '"pageSize":20,"sortType":10,"consolidateTypeList":[1],"mobile":""}'
    )
    out = _normalize_orders_post_data(post)
    assert out is not None
    payload = json.loads(out)
    assert payload["orderType"] == 0
    assert payload["afterSaleType"] == 0
    assert payload["sortType"] == 1
    assert "consolidateTypeList" not in payload
    assert payload["groupStartTime"] == 1780033080
    assert payload["pageSize"] == 20
    assert _normalize_orders_post_data("not-json") is None
    assert _normalize_orders_post_data(None) is None
