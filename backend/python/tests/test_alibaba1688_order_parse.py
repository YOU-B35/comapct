"""1688 consumer-order Day0 gate + fixture sanity tests."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from agent.alibaba1688_order_constants import (
    ORDERS_XHR_READY,
    assert_orders_xhr_ready,
)
from agent.alibaba1688_order_tasks import (
    _cents_to_yuan,
    _date_range,
    _default_window,
    _parse_order_list_response,
    _parse_refund_list_response,
    normalize_order,
    normalize_refund,
)


def test_orders_xhr_gate_is_ready() -> None:
    assert ORDERS_XHR_READY is True
    assert_orders_xhr_ready()  # no raise


def test_day0_attachment_has_required_fields() -> None:
    attachment = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "superpowers"
        / "specs"
        / "attachments"
        / "1688-consumer-orders-xhr.md"
    )
    assert attachment.exists()
    text = attachment.read_text(encoding="utf-8")
    for key in ("mtop.1688.trading.dataline.service", "sellerOrderList", "gmtPayment", "orderDateTime", "mtop.1688.dw.refund.list"):
        assert key in text, key


def test_order_fixtures_exist() -> None:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / "alibaba1688"
    for name in ("order_list_page1.json", "order_paid.json", "order_unpaid.json", "refund_list.json"):
        p = fixture_dir / name
        assert p.exists(), name
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data, name


def test_paid_fixture_has_payment_fields() -> None:
    p = Path(__file__).resolve().parent / "fixtures" / "alibaba1688" / "order_paid.json"
    order = json.loads(p.read_text(encoding="utf-8"))
    assert order.get("gmtPayment")
    assert order.get("sumPayment") not in (None, "", "0")
    assert order.get("status") == "waitsellersend"
    assert order.get("orderEntries")


def test_unpaid_fixture_has_no_payment_time() -> None:
    p = Path(__file__).resolve().parent / "fixtures" / "alibaba1688" / "order_unpaid.json"
    order = json.loads(p.read_text(encoding="utf-8"))
    assert order.get("status") == "waitbuyerpay"
    assert not order.get("gmtPayment")


def test_buyer_info_is_masked_in_fixtures() -> None:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / "alibaba1688"
    for name in ("order_list_page1.json", "order_paid.json", "refund_list.json"):
        text = (fixture_dir / name).read_text(encoding="utf-8")
        assert "MASKED" in text or "永信砖" not in text, name


def _load(name: str):
    p = Path(__file__).resolve().parent / "fixtures" / "alibaba1688" / name
    return json.loads(p.read_text(encoding="utf-8"))


def test_normalize_paid_order_from_fixture() -> None:
    raw = _load("order_paid.json")
    out = normalize_order(raw)
    assert out["order"]["order_no"] == str(raw["id"])
    assert out["order"]["status"] == "paid"
    assert out["order"]["paid_amount"] == "53.25"  # 平台分 -> 元（5325分 = 53.25元）
    assert out["order"]["paid_at"].startswith("2026-")
    assert out["order"]["buyer_masked"].endswith("***")
    assert out["items"]
    first = out["items"][0]
    assert first["line_id"] == raw["orderEntries"][0]["entryId"]
    assert first["offer_id"] == str(raw["orderEntries"][0]["sourceId"])
    assert first["paid_amount"] == "38.25"  # 3825分 = 38.25元
    assert first["unit_price"] == "0.85"  # 85分 = 0.85元
    assert first["quantity"] == "45"
    assert "颜色" in first["sku_text"]
    assert first["image_url"].startswith("https://")


def test_normalize_unpaid_order_has_no_paid_time() -> None:
    raw = _load("order_unpaid.json")
    out = normalize_order(raw)
    assert out["order"]["status"] == "unpaid"
    assert out["order"]["paid_at"] == ""
    assert out["order"]["paid_amount"] == "0"


def test_normalize_multi_item_order_from_page_fixture() -> None:
    rows = _load("order_list_page1.json")
    multi = next((o for o in rows if len(o.get("orderEntries") or []) > 1), None)
    assert multi is not None
    out = normalize_order(multi)
    assert len(out["items"]) == len(multi["orderEntries"])


def test_normalize_refund_from_fixture() -> None:
    items = _load("refund_list.json")
    assert items
    first = normalize_refund(items[0])
    assert first["refund_no"] == items[0]["refundId"]
    assert first["order_no"] == items[0]["orderId"]
    assert first["refunded_amount"] == "64"  # 6400分 = 64元
    assert first["refunded_at"].startswith("2026-")
    assert first["refund_status"] == items[0]["refundStatusEnum"]


def test_refund_date_cross_day_is_preserved() -> None:
    # 跨日退款：applyTime 日期即扣减日，不依赖订单支付日
    refund = normalize_refund({"refundId": "TQ1", "orderId": "O1", "applyTime": "2026-08-13 14:14:38", "totalRefundFee": "6400"})
    assert refund["refunded_at"] == "2026-08-13 14:14:38"
    assert refund["refunded_amount"] == "64"


def test_cents_to_yuan_conversion() -> None:
    assert _cents_to_yuan("5325") == "53.25"
    assert _cents_to_yuan("100") == "1"
    assert _cents_to_yuan("0") == "0"
    assert _cents_to_yuan("") == "0"
    assert _cents_to_yuan(None) == "0"
    assert _cents_to_yuan("6400") == "64"


def test_date_range_format_matches_day0() -> None:
    assert _date_range("2026-08-12", "2026-08-19") == "2026-08-12 00:00:00~2026-08-19 23:59:59"
    assert _date_range("", "2026-08-19") == ""


def test_default_window_is_seven_days() -> None:
    start, end = _default_window(7)
    assert start <= end
    assert start[:4] == end[:4] == datetime.now().strftime("%Y")[:4]


def test_parse_order_list_response_uses_day0_shape() -> None:
    resp = {
        "ret": ["SUCCESS::调用成功"],
        "data": {"data": {"result": json.dumps({"data": {"data": [{"idStr": "O1"}], "total": 1473, "pages": 148, "pageSize": 10}})}},
    }
    rows, total = _parse_order_list_response(resp)
    assert total == 1473
    assert rows[0]["idStr"] == "O1"


def test_parse_order_list_response_rejects_non_success() -> None:
    rows, total = _parse_order_list_response({"ret": ["FAIL_SYS_USER_VALIDATE"], "data": {}})
    assert rows == []
    assert total == 0


def test_parse_refund_list_response_uses_day0_shape() -> None:
    resp = {
        "ret": ["SUCCESS::调用成功"],
        "data": {"model": {"data": [{"refundId": "TQ1"}], "totalCount": "2"}},
    }
    rows, total = _parse_refund_list_response(resp)
    assert total == 2
    assert rows[0]["refundId"] == "TQ1"
