"""Regression tests for PDD per-day order fetching."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import agent.pdd_tasks as pdd_tasks
from agent.pdd_tasks import (
    SHANGHAI,
    _fetch_orders_by_day,
    _order_rows_from_payload,
    _save_pdd_failed_days,
)


class _FakeResponse:
    status = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeRequestContext:
    def __init__(self, payload):
        self._payload = payload

    def post(self, url, *, headers=None, data=None, timeout=None):
        return _FakeResponse(self._payload)


class _FakePage:
    def __init__(self, payload):
        self.request = _FakeRequestContext(payload)


class _RecordingBucket:
    def __init__(self):
        self.consumed: list[float] = []

    def consume(self, tokens: float = 1.0) -> None:
        self.consumed.append(tokens)


def test_order_rows_from_payload_returns_empty_when_no_rows():
    assert _order_rows_from_payload({}) == []
    assert _order_rows_from_payload({"result": {"errorMsg": "rate limited"}}) == []


def test_order_rows_from_payload_maps_valid_rows():
    payload = {
        "result": {
            "orderList": [
                {
                    "orderSn": "PDD123",
                    "goodsList": [{"goodsName": "demo sku", "goodsNum": 2, "goodsPrice": "1.00"}],
                    "payAmount": "2.00",
                    "createTime": 1720000000,
                    "status": "1",
                }
            ]
        }
    }
    rows = _order_rows_from_payload(payload)
    assert len(rows) == 1
    assert rows[0]["order_no"] == "PDD123"


def test_fetch_orders_by_day_consumes_bucket_per_day():
    payload = {
        "result": {
            "orderList": [
                {
                    "orderSn": "PDD123",
                    "goodsList": [{"goodsName": "demo sku", "goodsNum": 2, "goodsPrice": "1.00"}],
                    "payAmount": "2.00",
                    "createTime": 1720000000,
                    "status": "1",
                }
            ]
        }
    }
    bucket = _RecordingBucket()
    rows, meta = _fetch_orders_by_day(
        _FakePage(payload),
        url="https://mms.pinduoduo.com/mangkhut/mms/recentOrderList",
        headers={},
        post_data="{}",
        date_window="d1",
        days=["2026-08-30"],
        bucket=bucket,
    )
    assert len(rows) == 1
    assert bucket.consumed == [1.0]


def test_fetch_orders_by_day_marks_null_response_failed():
    """Null body（签名过期/未登录时平台返回 null）必须算失败日，不能当成“无订单”。"""
    bucket = _RecordingBucket()
    rows, meta = _fetch_orders_by_day(
        _FakePage(None),
        url="https://mms.pinduoduo.com/mangkhut/mms/recentOrderList",
        headers={},
        post_data="{}",
        date_window="d1",
        days=["2026-08-30"],
        bucket=bucket,
    )
    assert rows == []
    assert meta["failed_days"] == ["2026-08-30"]
    assert meta["truncated"] is True


def test_fetch_orders_by_day_marks_error_body_failed():
    """错误响应体（success=false / 无订单列表结构）不能算成功空日。"""
    bucket = _RecordingBucket()
    rows, meta = _fetch_orders_by_day(
        _FakePage({"success": False, "errorMsg": "操作太过频繁，请稍后再试"}),
        url="https://mms.pinduoduo.com/mangkhut/mms/recentOrderList",
        headers={},
        post_data="{}",
        date_window="d1",
        days=["2026-08-30"],
        bucket=bucket,
    )
    assert rows == []
    assert meta["failed_days"] == ["2026-08-30"]


def test_fetch_orders_by_day_empty_day_is_success():
    """真正的空列表（result.orderList=[]）算成功空日，不算失败。"""
    bucket = _RecordingBucket()
    rows, meta = _fetch_orders_by_day(
        _FakePage({"result": {"orderList": []}}),
        url="https://mms.pinduoduo.com/mangkhut/mms/recentOrderList",
        headers={},
        post_data="{}",
        date_window="d1",
        days=["2026-08-30"],
        bucket=bucket,
    )
    assert rows == []
    assert meta["failed_days"] == []
    assert meta["truncated"] is False


def test_fetch_orders_by_day_aborts_after_consecutive_failures():
    """连续失败达到上限后提前结束，并把剩余日期记为失败日，避免烧掉整窗口时间。"""
    bucket = _RecordingBucket()
    days = ["2026-08-28", "2026-08-29", "2026-08-30", "2026-08-31"]
    rows, meta = _fetch_orders_by_day(
        _FakePage(None),
        url="https://mms.pinduoduo.com/mangkhut/mms/recentOrderList",
        headers={},
        post_data="{}",
        date_window="d1",
        days=days,
        bucket=bucket,
        max_consecutive_failures=2,
    )
    assert rows == []
    # 只消耗了前两天的 pacing，剩余日期原样保留给下次补齐
    assert bucket.consumed == [1.0, 1.0]
    assert meta["failed_days"] == ["2026-08-31", "2026-08-30", "2026-08-29", "2026-08-28"]
    assert meta["truncated"] is True


def test_fetch_orders_by_day_iterates_newest_first():
    """按天抓取必须从今天往前：请求顺序为日期倒序（今天 → 昨天 → …）。"""
    requested: list[str] = []

    class _CaptureRequest:
        def post(self, url, *, headers=None, data=None, timeout=None):
            payload = json.loads(data or "{}")
            start_ts = int(payload.get("groupStartTime") or 0)
            day = datetime.fromtimestamp(start_ts, tz=SHANGHAI).date().isoformat()
            requested.append(day)
            return _FakeResponse({"result": {"orderList": []}})

    class _CapturePage:
        request = _CaptureRequest()

    bucket = _RecordingBucket()
    days = ["2026-08-28", "2026-08-29", "2026-08-30"]
    _fetch_orders_by_day(
        _CapturePage(),
        url="https://mms.pinduoduo.com/mangkhut/mms/recentOrderList",
        headers={},
        post_data="{}",
        date_window="d7",
        days=days,
        bucket=bucket,
    )
    assert requested == ["2026-08-30", "2026-08-29", "2026-08-28"]


def test_save_failed_days_clamps_to_current_window(monkeypatch, tmp_path):
    """失败的日期必须裁剪到当前窗口内，避免越界日期被反复请求。"""
    cache = tmp_path / ".pdd-xhr-cache.json"
    monkeypatch.setattr(pdd_tasks, "_pdd_xhr_cache_path", lambda: cache)
    today = datetime.now(SHANGHAI).date()
    inside = (today - timedelta(days=5)).isoformat()
    outside = (today - timedelta(days=40)).isoformat()
    _save_pdd_failed_days("orders", "d30", [outside, inside])
    data = json.loads(cache.read_text(encoding="utf-8"))
    assert data["orders"]["failed_days"] == [inside]
    assert data["orders"]["window"] == "d30"
