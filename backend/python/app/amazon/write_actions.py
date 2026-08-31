"""Amazon Seller Central 写操作（紫鸟 WebDriver）。"""
from __future__ import annotations

import re
from typing import Any

from app.amazon.page_urls import MESSAGES_URL, ORDERS_URL
from app.amazon.report_crawler import AmazonLoginRequiredError
from app.amazon.session_context import (
    extract_debug_port,
    goto as _goto,
    require_seller_logged_in as _require_seller_logged_in,
    save_capture as _save_capture,
)
from app.ziniao.client import ZiniaoClient, ZiniaoConfig

SHIP_ACTION_LABELS = (
    "Confirm shipment",
    "确认发货",
    "Mark as shipped",
    "Buy shipping",
    "Edit shipment",
    "Ship now",
)
SUBMIT_LABELS = ("Confirm shipment", "确认发货", "Ship", "Save", "Submit", "提交", "保存")
REVIEW_ACTION_LABELS = (
    "Mark as resolved",
    "Contact buyer",
    "Respond",
    "Reply",
    "已处理",
    "联系买家",
)
CASE_ACTION_LABELS = ("Mark as read", "Acknowledge", "标记已读", "已读")

TRACKING_INPUT_SELECTORS = [
    "input[name*='tracking' i]",
    "input[id*='tracking' i]",
    "input[placeholder*='tracking' i]",
    "input[aria-label*='tracking' i]",
    "input[data-testid*='tracking' i]",
    "input[name*='trackingNumber' i]",
    "input[name*='carrier' i]",
    "input[id*='carrier' i]",
    "input[placeholder*='carrier' i]",
    "input[aria-label*='carrier' i]",
    "input[placeholder*='运单' i]",
    "input[aria-label*='运单' i]",
    "input[placeholder*='追踪' i]",
    "input[aria-label*='追踪' i]",
    "input[name*='shipment' i]",
]


def supports_ship_action(fulfillment_type: Any) -> bool:
    """FBA 订单由亚马逊履约，无需在卖家后台确认发货。"""
    value = str(fulfillment_type or "").strip().lower()
    if not value:
        return True
    return value not in {"fba", "amazon"}


def execute_amazon_write(
    *,
    action: str,
    browser_id: str = "",
    browser_oauth: str = "",
    store_name: str = "",
    item_payload: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not browser_id and not browser_oauth:
        raise ValueError("缺少 browser_id 或 browser_oauth")

    normalized = (action or "").strip().lower()
    payload = item_payload if isinstance(item_payload, dict) else {}
    req = request if isinstance(request, dict) else {}

    ziniao = ZiniaoClient(ZiniaoConfig.from_env())
    ziniao.ensure_webdriver_client(wait_seconds=20)
    start_result = ziniao.start_browser(
        browser_id=browser_id or None,
        browser_oauth=browser_oauth or None,
    )
    debug_port = extract_debug_port(start_result)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("缺少 playwright") from exc

    result: dict[str, Any] = {
        "action": normalized,
        "platform_confirmed": False,
        "page_url": "",
        "capture_path": "",
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
        try:
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(90000)

            if normalized == "buyer_message_reply":
                _write_buyer_message_reply(page, payload, req, store_name=store_name, result=result)
            elif normalized == "outbound_ship":
                _write_outbound_ship(page, payload, req, store_name=store_name, result=result)
            elif normalized == "review_handle":
                _write_review_handle(page, payload, req, store_name=store_name, result=result)
            elif normalized == "case_ack":
                _write_case_ack(page, payload, req, store_name=store_name, result=result)
            else:
                raise RuntimeError(f"未支持的写操作: {normalized}")
        finally:
            browser.close()

    if not result.get("platform_confirmed"):
        raise RuntimeError("AMAZON_WRITE_DOM_FAILED: 未能在 Seller Central 确认写操作")
    return result


def _open_order_context(page, order_no: str) -> None:
    if not order_no:
        return
    search = page.locator(
        "input[type='search'], input[placeholder*='Search' i], input[name*='search' i], input[id*='search' i]"
    ).first
    if search.count() > 0:
        search.click(timeout=5000)
        search.fill(order_no)
        page.keyboard.press("Enter")
        page.wait_for_timeout(2500)
    target = page.get_by_text(order_no, exact=False).first
    if target.count() > 0:
        target.click(timeout=15000)
        page.wait_for_timeout(1500)


def _click_first_action(page, labels: tuple[str, ...]) -> bool:
    for label in labels:
        button = page.get_by_role("button", name=re.compile(label, re.I))
        if button.count() > 0:
            button.first.click(timeout=10000)
            page.wait_for_timeout(1500)
            return True
        link = page.get_by_role("link", name=re.compile(label, re.I))
        if link.count() > 0:
            link.first.click(timeout=10000)
            page.wait_for_timeout(1500)
            return True
    return False


def _find_tracking_input(page):
    """优先在发货弹窗内查找，其次整页；避免兜底抓到页面搜索框。"""
    scopes = [
        page.get_by_role("dialog"),
        page.locator("kat-dialog"),
        page.locator("awd-dialog"),
        page,
    ]
    for scope in scopes:
        for selector in TRACKING_INPUT_SELECTORS:
            locator = scope.locator(selector).first
            if locator.count() > 0:
                return locator
        # 弹窗内的任意可见文本框兜底（弹窗内一般没有搜索框）
        if scope is not page:
            textbox = scope.get_by_role("textbox").first
            if textbox.count() > 0:
                return textbox
    return None


def _write_buyer_message_reply(
    page,
    payload: dict[str, Any],
    request: dict[str, Any],
    *,
    store_name: str,
    result: dict[str, Any],
) -> None:
    body = _goto(page, MESSAGES_URL)
    _require_seller_logged_in(page, body, store_name=store_name)
    order_no = str(payload.get("order_no") or payload.get("orderNo") or "").strip()
    note = str(request.get("note") or "").strip()
    template_id = str(request.get("template_id") or request.get("templateId") or "").strip()

    if order_no:
        page.get_by_text(order_no, exact=False).first.click(timeout=15000)
    page.wait_for_timeout(1500)

    textarea = page.locator("textarea").first
    if textarea.count() == 0:
        result["capture_path"] = _save_capture(page, store_name=store_name, suffix="write_msg_no_textarea")
        raise RuntimeError("AMAZON_WRITE_DOM_FAILED: 未找到消息回复输入框")

    reply_text = note or template_id or "Thank you for your message."
    textarea.fill(reply_text)
    page.wait_for_timeout(500)
    _click_first_action(page, ("Send", "发送", "Reply", "回复"))

    result["page_url"] = page.url
    result["capture_path"] = _save_capture(page, store_name=store_name, suffix="write_msg_done")
    result["platform_confirmed"] = True


def _write_outbound_ship(
    page,
    payload: dict[str, Any],
    request: dict[str, Any],
    *,
    store_name: str,
    result: dict[str, Any],
) -> None:
    body = _goto(page, ORDERS_URL)
    _require_seller_logged_in(page, body, store_name=store_name)
    order_no = str(payload.get("order_no") or payload.get("orderNo") or "").strip()
    tracking_no = str(request.get("tracking_no") or request.get("trackingNo") or "").strip()
    if not tracking_no:
        raise ValueError("运单号不能为空")
    fulfillment_type = payload.get("fulfillment_type") or payload.get("fulfillmentType") or ""
    if not supports_ship_action(fulfillment_type):
        result["capture_path"] = _save_capture(page, store_name=store_name, suffix="write_ship_fba")
        raise RuntimeError(
            f"AMAZON_WRITE_FBA_ORDER: 订单 {order_no or '-'} 为 FBA 履约，无需确认发货"
        )

    _open_order_context(page, order_no)
    clicked = _click_first_action(page, SHIP_ACTION_LABELS)
    if not clicked:
        result["capture_path"] = _save_capture(page, store_name=store_name, suffix="write_ship_no_action")
        raise RuntimeError("AMAZON_WRITE_DOM_FAILED: 未找到确认发货入口（订单可能已发货或为 FBA）")
    page.wait_for_timeout(2500)

    tracking_input = _find_tracking_input(page)
    if tracking_input is None or tracking_input.count() == 0:
        result["capture_path"] = _save_capture(page, store_name=store_name, suffix="write_ship_no_input")
        raise RuntimeError("AMAZON_WRITE_DOM_FAILED: 未找到运单号输入框")

    tracking_input.fill(tracking_no)
    page.wait_for_timeout(500)
    clicked = _click_first_action(page, SUBMIT_LABELS)
    if not clicked:
        result["capture_path"] = _save_capture(page, store_name=store_name, suffix="write_ship_no_submit")
        raise RuntimeError("AMAZON_WRITE_DOM_FAILED: 未找到确认提交按钮")

    result["page_url"] = page.url
    result["capture_path"] = _save_capture(page, store_name=store_name, suffix="write_ship_done")
    result["platform_confirmed"] = True


def _write_review_handle(page, payload: dict[str, Any], request: dict[str, Any], *, store_name: str, result: dict[str, Any]) -> None:
    from app.amazon.report_crawler import REVIEWS_URL

    body = _goto(page, REVIEWS_URL)
    _require_seller_logged_in(page, body, store_name=store_name)
    order_no = str(payload.get("order_no") or payload.get("orderNo") or "").strip()
    product_name = str(payload.get("product_name") or payload.get("productName") or "").strip()
    if order_no:
        page.get_by_text(order_no, exact=False).first.click(timeout=15000)
        page.wait_for_timeout(1500)
    elif product_name:
        page.get_by_text(product_name[:40], exact=False).first.click(timeout=15000)
        page.wait_for_timeout(1500)

    note = str(request.get("note") or "").strip()
    textarea = page.locator("textarea").first
    if textarea.count() > 0 and note:
        textarea.fill(note)
        page.wait_for_timeout(500)

    clicked = _click_first_action(page, REVIEW_ACTION_LABELS)
    if not clicked and textarea.count() == 0:
        result["capture_path"] = _save_capture(page, store_name=store_name, suffix="write_review_no_action")
        raise RuntimeError("AMAZON_WRITE_DOM_FAILED: 未找到差评处理入口")

    result["page_url"] = page.url
    result["capture_path"] = _save_capture(page, store_name=store_name, suffix="write_review_done")
    result["platform_confirmed"] = True
    result["note"] = note


def _write_case_ack(page, payload: dict[str, Any], request: dict[str, Any], *, store_name: str, result: dict[str, Any]) -> None:
    case_url = str(payload.get("case_url") or payload.get("url") or "").strip()
    case_id = str(payload.get("case_id") or payload.get("caseId") or "").strip()
    if case_url:
        body = _goto(page, case_url)
        _require_seller_logged_in(page, body, store_name=store_name)
    elif case_id:
        page.get_by_text(case_id, exact=False).first.click(timeout=15000)
        page.wait_for_timeout(1500)

    clicked = _click_first_action(page, CASE_ACTION_LABELS)
    if not clicked:
        checkbox = page.locator("input[type='checkbox']").first
        if checkbox.count() > 0:
            checkbox.check(timeout=5000)
            clicked = True

    if not clicked:
        result["capture_path"] = _save_capture(page, store_name=store_name, suffix="write_case_no_action")
        raise RuntimeError("AMAZON_WRITE_DOM_FAILED: 未找到 Case 已读入口")

    result["page_url"] = page.url
    result["capture_path"] = _save_capture(page, store_name=store_name, suffix="write_case_done")
    result["platform_confirmed"] = True
    result["note"] = str(request.get("note") or "")
