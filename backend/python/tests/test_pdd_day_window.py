"""Regression tests for PDD per-day order fetching."""
from __future__ import annotations

from agent.pdd_tasks import _fetch_orders_by_day, _order_rows_from_payload


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
