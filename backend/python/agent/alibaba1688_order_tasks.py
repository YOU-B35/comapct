"""1688 consumer-order normalization helpers (Day0-verified fields)."""
from __future__ import annotations

import json
import hashlib
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from agent.alibaba1688_order_constants import (
    ORDER_LIST_API,
    ORDER_LIST_PAGE_SIZE,
    ORDER_LIST_SERVICE_ID,
    REFUND_LIST_API,
    TRADE_STATUS_MAP,
    assert_orders_xhr_ready,
)
from agent.alibaba1688_tasks import _close, _launch, _looks_logged_in

_CN = timezone(timedelta(hours=8), name="Asia/Shanghai")


def _epoch_ms_to_text(value: Any) -> str:
    """gmtPayment epoch millis -> 'YYYY-MM-DD HH:mm:ss' (Asia/Shanghai)."""
    if value in (None, "", 0, "0"):
        return ""
    try:
        ms = int(value)
    except (TypeError, ValueError):
        return ""
    if ms <= 0:
        return ""
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=_CN).strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return ""


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _cents_to_yuan(value: Any) -> str:
    """平台金额单位为分；统一转为元字符串（如 '5325' -> '53.25'）。"""
    text_value = _text(value, "0")
    if not text_value:
        return "0"
    try:
        cents = Decimal(text_value)
    except Exception:
        return "0"
    yuan = cents / Decimal(100)
    formatted = format(yuan, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


def _masked_buyer(raw: dict[str, Any]) -> str:
    info = raw.get("buyerInfo") or {}
    if not isinstance(info, dict):
        return ""
    login = _text(info.get("loginId") or info.get("nick") or "")
    if not login:
        return ""
    return login[:1] + "***"


def _quantity_text(value: Any) -> str:
    """Platform quantity is a model dict: prefer realAmountStr/calAmount."""
    if isinstance(value, dict):
        for key in ("realAmountStr", "calAmount", "realAmount"):
            if value.get(key) not in (None, ""):
                return str(value[key])
        return "0"
    return _text(value, "0")


def _spec_text(value: Any) -> str:
    """specInfo is a dict with specItems; join readable values."""
    if isinstance(value, dict):
        items = value.get("specItems") or []
        parts = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = _text(item.get("specName"))
            spec_value = _text(item.get("specValue"))
            if spec_value:
                parts.append(f"{name}:{spec_value}" if name else spec_value)
        return " / ".join(parts)
    return _text(value)


def normalize_item(raw: dict[str, Any]) -> dict[str, Any]:
    image = _text(raw.get("mainSummImageUrl"))
    if image.startswith("http://"):
        image = "https://" + image[7:]
    elif image.startswith("//"):
        image = "https:" + image
    return {
        "line_id": _text(raw.get("entryId")),
        "offer_id": _text(raw.get("sourceId") or raw.get("productNumber")),
        "sku_id": _text(raw.get("specId")),
        "sku_text": _spec_text(raw.get("specInfo")),
        "product_name": _text(raw.get("productName")),
        "quantity": _quantity_text(raw.get("quantity")),
        "paid_amount": _cents_to_yuan(raw.get("amount")),
        "unit_price": _cents_to_yuan(raw.get("actualUnitPrice")),
        "image_url": image,
    }


def normalize_order(raw: dict[str, Any]) -> dict[str, Any]:
    """Return {'order': {...}, 'items': [...]} for one platform order."""
    status_raw = _text(raw.get("status"))
    status = TRADE_STATUS_MAP.get(status_raw, status_raw)
    seller = raw.get("sellerInfo") or {}
    seller_name = ""
    seller_id = ""
    if isinstance(seller, dict):
        seller_name = _text(seller.get("companyName"))
        seller_id = _text(seller.get("userId"))
    return {
        "order": {
            "order_no": _text(raw.get("idStr") or raw.get("id")),
            "status": status,
            "paid_amount": _cents_to_yuan(raw.get("sumPayment")),
            "paid_at": _epoch_ms_to_text(raw.get("gmtPayment")),
            "created_platform_at": _text(raw.get("gmtCreate")),
            "updated_platform_at": _text(raw.get("gmtCreate")),
            "buyer_masked": _masked_buyer(raw),
            "seller_name": seller_name,
            "seller_id": seller_id,
        },
        "items": [normalize_item(entry) for entry in (raw.get("orderEntries") or []) if isinstance(entry, dict)],
    }


def normalize_refund(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "refund_no": _text(raw.get("refundId")),
        "order_no": _text(raw.get("orderId")),
        "refunded_at": _text(raw.get("applyTime")),
        "refunded_amount": _cents_to_yuan(raw.get("totalRefundFee")),
        "refund_status": _text(raw.get("refundStatusEnum")),
        "refund_status_text": _text(raw.get("refundStatusText")),
        "product_name": _text((raw.get("refundItemInfoList") or [{}])[0].get("skuName")),
    }


def normalize_orders_payload(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assert_orders_xhr_ready()
    return [normalize_order(row) for row in rows if isinstance(row, dict)]


def _date_range(start: str, end: str) -> str:
    s = str(start or "").strip()
    e = str(end or "").strip()
    if not s or not e:
        return ""
    return f"{s} 00:00:00~{e} 23:59:59"


def _default_window(days: int = 7) -> tuple[str, str]:
    today = datetime.now(_CN)
    end = today
    start = today - timedelta(days=max(0, days - 1))
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


APP_KEY = "12574478"


def _m_h5_tk(context) -> str:
    try:
        cookies = context.cookies()
    except Exception:
        cookies = []
    for c in cookies:
        if c.get("name") == "_m_h5_tk" and c.get("value"):
            return str(c["value"]).split("_")[0]
    return ""


def _mtop(page, api: str, data: dict[str, Any], timeout_ms: int = 30000) -> dict[str, Any]:
    """Call mtop with standard token signing via an in-page fetch."""
    token = _m_h5_tk(page.context)
    if not token:
        raise RuntimeError("A1688_ORDERS_SOURCE_UNAVAILABLE: 缺少 mtop token")
    api_name = api[5:] if api.startswith("mtop.") else api
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    t = str(int(time.time() * 1000))
    sign = hashlib.md5(f"{token}&{t}&{APP_KEY}&{data_json}".encode()).hexdigest()
    url = (
        f"https://h5api.m.1688.com/h5/mtop.{api_name}/1.0/"
        f"?jsv=2.7.0&appKey={APP_KEY}&t={t}&sign={sign}"
        f"&api=mtop.{api_name}&v=1.0&ecode=1"
        "&type=originaljson&dataType=json&data=" + quote(data_json, safe="")
    )
    result = page.evaluate(
        """async ({ url, timeoutMs }) => {
            const ctrl = new AbortController();
            const timer = setTimeout(() => ctrl.abort(), timeoutMs);
            try {
                const resp = await fetch(url, {
                    credentials: 'include',
                    headers: { 'Accept': 'application/json' },
                    signal: ctrl.signal,
                });
                return await resp.json();
            } catch (e) {
                return { ret: ['FAIL::' + String(e)] };
            } finally {
                clearTimeout(timer);
            }
        }""",
        {"url": url, "timeoutMs": timeout_ms},
    )
    if not isinstance(result, dict):
        raise RuntimeError("A1688_ORDERS_SOURCE_UNAVAILABLE: 订单接口无响应")
    ret = result.get("ret") or []
    if ret and "SUCCESS" not in str(ret[0]):
        raise RuntimeError(f"A1688_ORDERS_SOURCE_UNAVAILABLE: {ret[0]}")
    return result


def _parse_order_list_response(resp: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    data = (resp.get("data") or {}).get("data") if isinstance(resp.get("data"), dict) else {}
    result = data.get("result") if isinstance(data, dict) else None
    if not result:
        return [], 0
    try:
        inner = json.loads(result) if isinstance(result, str) else result
    except (TypeError, ValueError):
        return [], 0
    dd = inner.get("data") if isinstance(inner, dict) else None
    if not isinstance(dd, dict):
        return [], 0
    rows = dd.get("data") or []
    total = int(dd.get("total") or 0)
    return [row for row in rows if isinstance(row, dict)], total


def _parse_refund_list_response(resp: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    model = (resp.get("data") or {}).get("model") if isinstance(resp.get("data"), dict) else None
    if not isinstance(model, dict):
        return [], 0
    rows = model.get("data") or []
    total = int(model.get("totalCount") or 0)
    return [row for row in rows if isinstance(row, dict)], total


def run_orders_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    """Sync 1688 consumer orders + refunds and ingest via Java."""
    assert_orders_xhr_ready()
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    store_id = str(payload.get("store_id") or "").strip() or "default"
    start_date = str(payload.get("start_date") or "").strip()
    end_date = str(payload.get("end_date") or "").strip()
    if not start_date or not end_date:
        start_date, end_date = _default_window(7)
    sync_id = str(task.get("id") or payload.get("sync_id") or "")
    deadline = time.monotonic() + 300  # hard 5-minute task deadline

    pw = context = page = None
    started = time.monotonic()
    try:
        pw, context, page = _launch(
            tenant_id,
            headless=True,
            goto="https://work.1688.com/?_path_=sellerPro/2017sellerbase_trade/saleList",
            store_id=store_id,
        )
        if not _looks_logged_in(page, context):
            raise RuntimeError("A1688_NOT_LOGGED_IN: 1688 未登录或登录已失效，请重新打开登录窗口")
        page.wait_for_timeout(5000)

        date_range = _date_range(start_date, end_date)
        order_rows: list[dict[str, Any]] = []
        page_no = 1
        order_total = None
        partial = False
        while time.monotonic() < deadline:
            resp = _mtop(
                page,
                ORDER_LIST_API,
                {
                    "serviceId": ORDER_LIST_SERVICE_ID,
                    "param": json.dumps(
                        {
                            "page": page_no,
                            "pageSize": ORDER_LIST_PAGE_SIZE,
                            "tradeStatus": "",
                            "orderDateTime": date_range,
                        },
                        ensure_ascii=False,
                    ),
                },
            )
            rows, total = _parse_order_list_response(resp)
            if order_total is None:
                order_total = total
            order_rows.extend(rows)
            if not rows or len(order_rows) >= total:
                break
            page_no += 1
        else:
            partial = True
        if order_total is not None and len(order_rows) < order_total:
            partial = True

        refund_rows: list[dict[str, Any]] = []
        refund_page = 1
        refund_total = None
        while time.monotonic() < deadline:
            resp = _mtop(
                page,
                REFUND_LIST_API,
                {
                    "page": refund_page,
                    "isBuyer": False,
                    "pageSize": ORDER_LIST_PAGE_SIZE,
                    "timeoutSort": False,
                    "createTimeSort": True,
                    "diffRefundTypeCountRefunding": True,
                    "searchCondition": {"disputeStatusList": "all"},
                },
            )
            rows, total = _parse_refund_list_response(resp)
            if refund_total is None:
                refund_total = total
            refund_rows.extend(rows)
            if not rows or len(refund_rows) >= max(total, 1):
                break
            refund_page += 1
        if refund_total is not None and refund_rows and len(refund_rows) < refund_total:
            partial = True

        orders = normalize_orders_payload(order_rows)
        refunds = [normalize_refund(r) for r in refund_rows if isinstance(r, dict)]
        client.ingest_1688_orders(
            {
                "store_id": store_id,
                "sync_id": sync_id,
                "orders": orders,
                "refunds": refunds,
            }
        )
        return {
            "orders_count": len(orders),
            "items_count": sum(len(o.get("items") or []) for o in orders),
            "refunds_count": len(refunds),
            "start_date": start_date,
            "end_date": end_date,
            "partial": partial,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "logged_in": True,
        }
    finally:
        _close(pw, context)
