"""PDD direct-API pagination: replay page params instead of clicking next-page UI."""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from agent import pdd_tasks as mod


def _order_row(sn: str) -> dict:
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    ts = int(
        datetime(now.year, now.month, now.day, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp()
    ) + 3600
    return {
        "order_sn": sn,
        "goods_list": [{"goods_name": f"商品{sn}", "goods_num": 1, "goods_amount": 100}],
        "pay_amount": 100,
        "create_time": ts,
    }


def _product_row(gid: str) -> dict:
    return {
        "goods_id": gid,
        "goods_name": f"商品{gid}",
        "sku_price": 9900,
        "quantity": 10,
    }


def _page_payload(kind: str, rows: list[dict], total: int | None = None) -> dict:
    key = "orderList" if kind == "orders" else "goodsList"
    return {"data": {key: rows}, "total": total if total is not None else len(rows)}


class _Resp:
    def __init__(self, status: int, payload: dict | None = None):
        self.status = status
        self._payload = payload

    def json(self):
        return self._payload


class _FakePage:
    def __init__(self, direct_payload: dict | None = None, replay_payloads: list[dict] | None = None):
        self.direct_payload = direct_payload
        self.replay_payloads = replay_payloads or []
        self.post_calls: list[str] = []
        self.request = self

    def post(self, url, *, headers=None, data=None, timeout=None):
        self.post_calls.append(url)
        if self.direct_payload is None:
            return _Resp(404)
        return _Resp(200, self.direct_payload)


def _captured_orders() -> dict:
    payload = _page_payload("orders", [_order_row("O1"), _order_row("O2")], total=5)
    return {
        "method": "POST",
        "url": "https://mms.pinduoduo.com/mangkhut/mms/order/queryOrderList",
        "headers": {"content-type": "application/json;charset=UTF-8"},
        "post_data": json.dumps({"pageNum": 1, "pageSize": 100}),
        "payload": payload,
        "rows": [_order_row("O1"), _order_row("O2")],
    }


def test_fetch_paged_rows_orders_replays_pages_without_ui_click(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "_pdd_xhr_cache_path", lambda: tmp_path / "pdd-cache.json")
    page = _FakePage(
        direct_payload=_page_payload("orders", [_order_row("O1"), _order_row("O2")], total=5),
        replay_payloads=[_page_payload("orders", [_order_row("O3"), _order_row("O4")], total=5)],
    )
    capture_calls = {"n": 0}
    monkeypatch.setattr(
        mod,
        "_capture_xhr",
        lambda *a, **k: capture_calls.__setitem__("n", capture_calls["n"] + 1) or None,
    )
    monkeypatch.setattr(mod, "_load_pdd_xhr_cache", lambda kind: {})
    replay_calls: list[tuple[int, int]] = []

    def fake_replay(page, *, method, url, headers, post_data, page_no, page_size, kind=""):
        replay_calls.append((page_no, page_size))
        idx = page_no - 2
        if idx < len(page.replay_payloads):
            return page.replay_payloads[idx]
        return _page_payload("orders", [], total=0)

    monkeypatch.setattr(mod, "_replay_page", fake_replay)

    rows, source, meta = mod._fetch_paged_rows(
        page,
        kind="orders",
        page_urls=(mod.PDD_ORDER_LIST_PAGE,),
        api_candidates=mod.PDD_ORDER_LIST_API_CANDIDATES,
    )

    assert capture_calls["n"] == 0
    # 订单列表统一按 50 条/页重放（减少请求次数，规避平台频控）。
    assert replay_calls == [(2, 50), (3, 50)]
    assert {r["order_no"] for r in rows} == {"O1", "O2", "O3", "O4"}
    assert "recentOrderList" in source
    assert page.post_calls
    assert (tmp_path / "pdd-cache.json").exists()
    assert meta["total_hint"] == 5
    assert meta["truncated"] is False


def test_fetch_paged_rows_products_replays_and_dedupes(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "_pdd_xhr_cache_path", lambda: tmp_path / "pdd-cache.json")
    page = _FakePage(
        direct_payload=_page_payload("products", [_product_row("G1"), _product_row("G2")], total=3),
        replay_payloads=[_page_payload("products", [_product_row("G1"), _product_row("G3")], total=3)],
    )
    capture_calls = {"n": 0}
    monkeypatch.setattr(
        mod,
        "_capture_xhr",
        lambda *a, **k: capture_calls.__setitem__("n", capture_calls["n"] + 1) or None,
    )
    monkeypatch.setattr(mod, "_load_pdd_xhr_cache", lambda kind: {})
    replay_calls: list[tuple[int, int]] = []

    def fake_replay(page, *, method, url, headers, post_data, page_no, page_size, kind=""):
        replay_calls.append((page_no, page_size))
        idx = page_no - 2
        if idx < len(page.replay_payloads):
            return page.replay_payloads[idx]
        return _page_payload("products", [], total=0)

    monkeypatch.setattr(mod, "_replay_page", fake_replay)

    rows, _source, _meta = mod._fetch_paged_rows(
        page,
        kind="products",
        page_urls=(mod.PDD_PRODUCT_LIST_PAGE,),
        api_candidates=mod.PDD_PRODUCT_LIST_API_CANDIDATES,
    )

    assert capture_calls["n"] == 0
    assert {r["product_id"] for r in rows} == {"G1", "G2", "G3"}
    assert len(rows) == 3


def test_fetch_paged_rows_skips_capture_when_frozen_cache_works(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "_pdd_xhr_cache_path", lambda: tmp_path / "pdd-cache.json")
    cached_url = "https://mms.pinduoduo.com/mangkhut/mms/order/queryOrderList"
    mod._save_pdd_xhr_cache("orders", {"method": "POST", "url": cached_url})
    page = _FakePage(
        direct_payload=_page_payload("orders", [_order_row("O1")], total=2),
        replay_payloads=[_page_payload("orders", [_order_row("O2")], total=2)],
    )
    capture_calls = {"n": 0}
    monkeypatch.setattr(
        mod,
        "_capture_xhr",
        lambda *a, **k: capture_calls.__setitem__("n", capture_calls["n"] + 1) or None,
    )
    replay_calls: list[int] = []

    def fake_replay(page, *, method, url, headers, post_data, page_no, page_size, kind=""):
        replay_calls.append(page_no)
        idx = page_no - 2
        if idx < len(page.replay_payloads):
            return page.replay_payloads[idx]
        return _page_payload("orders", [], total=0)

    monkeypatch.setattr(mod, "_replay_page", fake_replay)

    rows, _source, _meta = mod._fetch_paged_rows(
        page,
        kind="orders",
        page_urls=(mod.PDD_ORDER_LIST_PAGE,),
        api_candidates=mod.PDD_ORDER_LIST_API_CANDIDATES,
    )

    assert capture_calls["n"] == 0
    assert page.post_calls[0] == cached_url
    assert replay_calls == [2]
    assert {r["order_no"] for r in rows} == {"O1", "O2"}


def test_pdd_xhr_cache_save_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_pdd_xhr_cache_path", lambda: tmp_path / "pdd-cache.json")

    mod._save_pdd_xhr_cache(
        "orders",
        {"method": "POST", "url": "https://mms.pinduoduo.com/mangkhut/mms/order/queryOrderList"},
    )
    mod._save_pdd_xhr_cache(
        "products",
        {"method": "GET", "url": "https://mms.pinduoduo.com/goods/goodsList"},
    )

    assert mod._load_pdd_xhr_cache("orders")["url"].endswith("queryOrderList")
    assert mod._load_pdd_xhr_cache("products")["method"] == "GET"
    assert mod._load_pdd_xhr_cache("issues") == {}


def test_fetch_paged_rows_page2_replay_failure_raises_for_orders(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "_pdd_xhr_cache_path", lambda: tmp_path / "pdd-cache.json")
    page = _FakePage(
        direct_payload=_page_payload("orders", [_order_row("O1"), _order_row("O2")], total=5),
    )
    monkeypatch.setattr(mod, "_load_pdd_xhr_cache", lambda kind: {})

    def fake_replay(page, *, page_no, **kwargs):
        # 首页重放成功（进入分页循环），第 2 页拒绝修改页码参数。
        if page_no == 1:
            return _page_payload("orders", [_order_row("O1"), _order_row("O2")], total=5)
        raise RuntimeError("signature mismatch")

    monkeypatch.setattr(mod, "_replay_page", fake_replay)

    try:
        mod._fetch_paged_rows(
            page,
            kind="orders",
            page_urls=(mod.PDD_ORDER_LIST_PAGE,),
            api_candidates=mod.PDD_ORDER_LIST_API_CANDIDATES,
        )
    except RuntimeError as exc:
        assert "PDD_ORDERS_SOURCE_UNAVAILABLE" in str(exc)
        assert "页码" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when the API rejects modified page params")


def _today_order_row(sn: str, offset_hours: int = 10) -> dict:
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    ts = int(
        datetime(now.year, now.month, now.day, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp()
    ) + offset_hours * 3600
    return {**_order_row(sn), "create_time": ts}


def test_fetch_paged_rows_orders_normalizes_recent_order_list_to_all(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "_pdd_xhr_cache_path", lambda: tmp_path / "pdd-cache.json")
    captured = {
        "method": "POST",
        "url": "https://mms.pinduoduo.com/mangkhut/mms/recentOrderList",
        "headers": {"content-type": "application/json;charset=UTF-8"},
        "post_data": json.dumps(
            {
                "orderType": 1,
                "afterSaleType": 1,
                "remarkStatus": -1,
                "urgeShippingStatus": -1,
                "groupStartTime": 1780033080,
                "groupEndTime": 1787809080,
                "pageNumber": 1,
                "pageSize": 20,
                "sortType": 10,
                "consolidateTypeList": [1],
                "mobile": "",
            }
        ),
        "payload": {
            "result": {
                "totalItemNum": 8237,
                "pageItems": [_today_order_row("O0")],
            }
        },
        "rows": [_today_order_row("O0")],
    }
    monkeypatch.setattr(mod, "_capture_xhr", lambda *a, **k: captured)
    monkeypatch.setattr(mod, "_load_pdd_xhr_cache", lambda kind: {})
    replayed_posts: list[dict] = []

    def fake_replay(page, *, method, url, headers, post_data, page_no, page_size, kind=""):
        body = json.loads(post_data)
        body = mod._set_page_in_payload(body, page_no, page_size)
        replayed_posts.append(body)
        assert page_size == 50
        assert body["orderType"] == 0
        assert body["afterSaleType"] == 0
        assert body["sortType"] == 1
        assert "consolidateTypeList" not in body
        assert body["groupStartTime"] == 1780033080
        assert body["groupEndTime"] == 1787809080
        assert body["pageNumber"] == page_no
        if page_no == 1:
            rows = [_today_order_row("O1"), _today_order_row("O2"), _today_order_row("O3")]
        else:
            # 第二页跨越今天边界，触发窗口起点早停。
            rows = [_today_order_row("O4"), _today_order_row("O5", offset_hours=-25)]
        return {"result": {"totalItemNum": 8237, "pageItems": rows}}

    monkeypatch.setattr(mod, "_replay_page", fake_replay)

    rows, source, _meta = mod._fetch_paged_rows(
        object(),
        kind="orders",
        page_urls=(mod.PDD_ORDER_LIST_PAGE,),
        api_candidates=(),
        date_window="today",
        skip_direct=True,
    )

    assert source == captured["url"]
    assert {r["order_no"] for r in rows} == {"O1", "O2", "O3", "O4", "O5"}
    assert replayed_posts[0]["pageNumber"] == 1
    assert replayed_posts[0]["pageSize"] == 50
    assert replayed_posts[1]["pageNumber"] == 2


def test_fetch_paged_rows_marks_truncated_when_page_fails_after_retries(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "_pdd_xhr_cache_path", lambda: tmp_path / "pdd-cache.json")
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    page = _FakePage(
        direct_payload=_page_payload("products", [_product_row("G1"), _product_row("G2")], total=50),
        replay_payloads=[_page_payload("products", [_product_row("G3")], total=50)],
    )
    monkeypatch.setattr(mod, "_capture_xhr", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_load_pdd_xhr_cache", lambda kind: {})

    calls = {"n": 0}

    def fake_replay(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            # 第 2 页成功（页大小=首屏行数 2），第 3 页起触发平台频控并重试耗尽
            return _page_payload("products", [_product_row("G3"), _product_row("G4")], total=50)
        raise RuntimeError("操作过于频繁，请稍后再试")

    monkeypatch.setattr(mod, "_replay_page", fake_replay)

    rows, _source, meta = mod._fetch_paged_rows(
        page,
        kind="products",
        page_urls=(mod.PDD_PRODUCT_LIST_PAGE,),
        api_candidates=mod.PDD_PRODUCT_LIST_API_CANDIDATES,
    )

    assert meta["truncated"] is True
    assert meta["total_hint"] == 50
    assert len(rows) == 4


def test_is_partial_sync_flags_rate_limited_or_skipped_runs():
    # 频控截断：平台有更多数据但未抓全
    assert mod._is_partial_sync(captured=100, platform_total=8197, truncated=True, skipped=0) is True
    # 未中断但数量仍少于平台总数
    assert mod._is_partial_sync(captured=100, platform_total=192, truncated=False, skipped=0) is True
    # 正常完成
    assert mod._is_partial_sync(captured=192, platform_total=192, truncated=False, skipped=0) is False
    # 未登录店铺跳过
    assert mod._is_partial_sync(captured=192, platform_total=192, truncated=False, skipped=1) is True
    # 平台未返回总数时以中断标记为准
    assert mod._is_partial_sync(captured=1, platform_total=0, truncated=False, skipped=0) is False


def test_sync_message_mentions_rate_limit_when_partial():
    msg = mod._sync_message("订单", 100, 1, 0, 8197)
    assert "100" in msg
    assert "8197" in msg
    assert "频控" in msg
    full = mod._sync_message("订单", 8197, 1, 0, 8197)
    assert "频控" not in full


def test_pdd_replay_headers_include_browser_fingerprint():
    headers = mod._pdd_replay_headers("orders", {})
    for key in (
        "accept-language",
        "sec-ch-ua",
        "sec-ch-ua-mobile",
        "sec-ch-ua-platform",
        "sec-fetch-dest",
        "sec-fetch-mode",
        "sec-fetch-site",
        "referer",
        "user-agent",
    ):
        assert headers.get(key), f"missing {key}"
    assert headers["referer"] == "https://mms.pinduoduo.com/orders/list"
    # 已捕获的签名/鉴权头优先生效
    merged = mod._pdd_replay_headers(
        "products",
        {"headers": {"x-anti-content": "sig-123", "user-agent": "UA-captured"}},
    )
    assert merged["x-anti-content"] == "sig-123"
    assert merged["user-agent"] == "UA-captured"


def test_fetch_orders_uses_cached_xhr_without_opening_page(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "_pdd_xhr_cache_path", lambda: tmp_path / "pdd-cache.json")
    cached = {
        "method": "POST",
        "url": "https://mms.pinduoduo.com/mangkhut/mms/recentOrderList",
        "headers": {"content-type": "application/json;charset=UTF-8", "x-anti-content": "sig-1"},
        "post_data": json.dumps(
            {
                "orderType": 1,
                "afterSaleType": 1,
                "pageNumber": 1,
                "pageSize": 20,
                "sortType": 10,
                "groupStartTime": 1780033080,
                "groupEndTime": 1787809080,
            }
        ),
        "updated_at": "2026-08-28 16:00:00",
    }
    monkeypatch.setattr(mod, "_load_pdd_xhr_cache", lambda kind: cached)
    capture_calls = {"n": 0}
    monkeypatch.setattr(
        mod,
        "_capture_xhr",
        lambda *a, **k: capture_calls.__setitem__("n", capture_calls["n"] + 1) or None,
    )
    replay_payload = _page_payload("orders", [_today_order_row("C1"), _today_order_row("C2")], total=2)

    def fake_replay(page, *, method, url, headers, post_data, page_no, page_size, kind=""):
        return replay_payload if page_no == 2 else _page_payload("orders", [], total=2)

    monkeypatch.setattr(mod, "_replay_page", fake_replay)

    rows, _source, meta = mod.fetch_orders_via_xhr(
        _FakePage(
            direct_payload=_page_payload(
                "orders", [_today_order_row("C1"), _today_order_row("C2")], total=2
            )
        ),
        date_window="today",
        store_id="s1",
    )
    assert capture_calls["n"] == 0
    assert meta["total_hint"] == 2
    assert {r["order_no"] for r in rows} == {"C1", "C2"}


def test_fetch_paged_rows_resumes_from_cached_last_page(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "_pdd_xhr_cache_path", lambda: tmp_path / "pdd-cache.json")
    cached = {
        "method": "POST",
        "url": "https://mms.pinduoduo.com/vodka/v2/mms/query/display/mall/goodsList",
        "headers": {"content-type": "application/json;charset=UTF-8"},
        "post_data": json.dumps({"pageNum": 1, "pageSize": 50}),
        "updated_at": "2026-08-28 16:00:00",
        "last_page": 3,
    }
    monkeypatch.setattr(mod, "_load_pdd_xhr_cache", lambda kind: cached)
    monkeypatch.setattr(mod, "_capture_xhr", lambda *a, **k: None)
    replay_calls: list[int] = []

    def fake_replay(page, *, method, url, headers, post_data, page_no, page_size, kind=""):
        replay_calls.append(page_no)
        if page_no <= 4:
            return _page_payload("products", [_product_row(f"G{page_no}")], total=5)
        if page_no == 5:
            return _page_payload("products", [_product_row("G5")], total=5)
        return _page_payload("products", [], total=5)

    monkeypatch.setattr(mod, "_replay_page", fake_replay)

    rows, _source, meta = mod._fetch_paged_rows(
        _FakePage(direct_payload=_page_payload("products", [_product_row("G0")], total=5)),
        kind="products",
        page_urls=(mod.PDD_PRODUCT_LIST_PAGE,),
        api_candidates=mod.PDD_PRODUCT_LIST_API_CANDIDATES,
    )
    assert replay_calls == [4, 5, 6]
    assert {r["product_id"] for r in rows} == {"G0", "G4", "G5"}
    assert meta["last_page"] == 5


def test_replay_with_retry_caps_attempts(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def fake_replay(*args, **kwargs):
        calls["n"] += 1
        raise RuntimeError("操作过于频繁，请稍后再试")

    monkeypatch.setattr(mod, "_replay_page", fake_replay)
    try:
        mod._replay_with_retry(
            None,
            method="POST",
            url="https://mms.pinduoduo.com/x",
            headers={},
            post_data="{}",
            page_no=3,
            page_size=50,
            kind="products",
        )
    except RuntimeError:
        pass
    assert calls["n"] == 2


def test_fetch_orders_by_day_marks_failed_days(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    posts: list[dict] = []

    class _Page:
        request = None

        def post(self, url, *, headers=None, data=None, timeout=None):
            body = json.loads(data)
            posts.append(body)
            if len(posts) == 1:
                return _Resp(
                    200,
                    {
                        "result": {
                            "totalItemNum": 1,
                            "pageItems": [_today_order_row("D1")],
                        }
                    },
                )
            raise RuntimeError("操作过于频繁，请稍后再试")

    page = _Page()
    page.request = page
    base_post = json.dumps(
        {
            "orderType": 0,
            "afterSaleType": 0,
            "sortType": 1,
            "pageNumber": 1,
            "pageSize": 50,
            "groupStartTime": 1,
            "groupEndTime": 2,
        }
    )
    rows, meta = mod._fetch_orders_by_day(
        page,
        url="https://mms.pinduoduo.com/mangkhut/mms/recentOrderList",
        headers={},
        post_data=base_post,
        date_window="d1",
    )
    # d1 = 2 天：从今天往前抓，首日成功，次日频控（2 次尝试）
    assert len(posts) == 3
    assert posts[0]["groupStartTime"] > posts[1]["groupStartTime"]
    assert meta["truncated"] is True
    assert len(meta["failed_days"]) == 1
    assert {r["order_no"] for r in rows} == {"D1"}
