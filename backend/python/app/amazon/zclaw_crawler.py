"""Read-only Amazon Seller Central crawl through the official Ziniao ZClaw CLI."""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from app.amazon.page_urls import HEALTH_URL, REPORT_URLS
from app.ziniao import cli_tools

HOME_URL = "https://sellercentral.amazon.com/amazonsell/business"
SCOPE_URLS = {
    "account_health": HEALTH_URL,
    "reports": REPORT_URLS[0],
    "daily": HOME_URL,
}


def _content_text(raw: Any) -> str:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return raw
    if not isinstance(raw, dict):
        return ""
    node: Any = raw
    for _ in range(4):
        if isinstance(node, str):
            return node
        if not isinstance(node, dict):
            return ""
        if any(key in node for key in ("headings", "links", "buttons", "bodyText", "text")):
            break
        child = None
        for key in ("data", "content"):
            candidate = node.get(key)
            if isinstance(candidate, (dict, str)):
                child = candidate
                break
        if child is None:
            break
        node = child
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ""
    legacy = node.get("bodyText") or node.get("text")
    if legacy:
        return str(legacy)
    parts = []
    for heading in node.get("headings") or []:
        if isinstance(heading, str) and heading.strip():
            parts.append(heading.strip())
    for item in (node.get("links") or []) + (node.get("buttons") or []):
        if isinstance(item, dict):
            text = (item.get("text") or "").strip()
            if text:
                parts.append(text)
    return "\n".join(parts) if parts else ""
def _metric(label: str, text: str, pattern: str) -> dict[str, str] | None:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return {"metric_key": re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_"), "label": label, "value": match.group(1).strip(), "status": "normal"}


def _dashboard_metrics(text: str) -> list[dict[str, str]]:
    patterns = (
        ("today_sales", r"已订购商品销售额\s*(US\$[\d,.]+)"),
        ("today_orders", r"已订购商品数量\s*([\d,]+)"),
        ("unresolved_orders", r"未解决的订单\s*([\d,]+)"),
        ("total_balance", r"总余额\s*(US\$[\d,.]+)"),
        ("ad_sales_7d", r"最近\s*7\s*天.{0,180}?带来的销售额\s*(US\$[\d,.]+)"),
        ("ad_spend_7d", r"最近\s*7\s*天.{0,260}?支出\s*(US\$[\d,.]+)"),
        ("ad_acos_7d", r"最近\s*7\s*天.{0,360}?广告支出回报\s*([\d,.]+)"),
    )
    return [row for label, pattern in patterns if (row := _metric(label, text, pattern))]


def _resolve_store_id(store_id: str, store_name: str) -> tuple[str, str]:
    if store_id:
        return store_id, "bound"
    listed = cli_tools.ziniao_store_list()
    if not listed.get("ok"):
        raise RuntimeError(listed.get("summary") or "无法读取紫鸟店铺列表")
    matches = [item for item in (listed.get("data") or []) if str(item.get("storeName") or "").strip() == store_name and "亚马逊" in str(item.get("platformName") or "")]
    if len(matches) != 1:
        raise RuntimeError("当前账号未绑定紫鸟店铺，且无法按店铺名称唯一匹配 Amazon 店铺")
    return str(matches[0].get("storeId") or ""), "name_match"



# Account health parser
def _account_health_metrics(text: str) -> list[dict[str, str]]:
    patterns = (
        ("account_health_status", r"账户状况\s*(?:为\s*)?((?:良好|健康|警告|预警|存在风险|不健康|healthy|good|warning|critical|unhealthy))"),
        ("account_health_rating", r"账户状况评级[^0-9]*?([0-9]+)"),
        ("order_defect_rate", r"订单缺陷率[^%]*?([0-9,.]+)%"),
        ("late_shipment_rate", r"迟发率[^%]*?([0-9,.]+)%"),
        ("valid_tracking_rate", r"有效追踪率[^%]*?([0-9,.]+)%"),
        ("on_time_delivery_rate", r"准时交货率[^%]*?([0-9,.]+)%"),
        ("ip_complaints", r"知识产权投诉[^0-9]*?([0-9]+)"),
        ("restricted_product_violations", r"违反受限商品政策[^0-9]*?([0-9]+)"),
        ("listing_policy_violations", r"上架政策违规[^0-9]*?([0-9]+)"),
    )
    return [row for label, pattern in patterns if (row := _metric(label, text, pattern))]
def _content_retry_count() -> int:
    try:
        return max(1, min(int(os.environ.get("AMAZON_ZCLAW_CONTENT_RETRIES", "8")), 10))
    except ValueError:
        return 8


def _content_retry_delay() -> float:
    try:
        return max(0.0, min(float(os.environ.get("AMAZON_ZCLAW_CONTENT_RETRY_DELAY_SECONDS", "1.5")), 10.0))
    except ValueError:
        return 1.5


def _page_content_ready(text: str, scope: str) -> bool:
    if not text.strip():
        return False
    low = text.lower()
    if any(marker in low for marker in ("正在加载", "loading...", "loading…", "please wait")):
        return False
    metrics = _account_health_metrics(text) if scope == "account_health" else _dashboard_metrics(text)
    if scope == "daily":
        return bool(metrics) and ("已订购商品销售额" in text or "今天到目前为止" in text)
    if scope == "account_health":
        return bool(metrics)
    return bool(metrics) or any(marker in low for marker in (
        "sellercentral.amazon.com", "seller central", "卖家平台", "我的业务", "账户状况"
    ))


def _read_ready_page_content(store_id: str, scope: str) -> tuple[dict[str, Any], str]:
    last_result: dict[str, Any] = {}
    last_text = ""
    attempts = _content_retry_count()
    for attempt in range(attempts):
        result = cli_tools.ziniao_page_content(store_id)
        last_result = result
        if result.get("ok"):
            last_text = _content_text(result.get("data"))
            if _page_content_ready(last_text, scope):
                return result, last_text
        if attempt < attempts - 1:
            time.sleep(_content_retry_delay())
    if not last_result.get("ok"):
        raise RuntimeError(last_result.get("summary") or "无法读取 Amazon 页面")
    return last_result, last_text


def crawl_zclaw_amazon(*, browser_id: str, store_name: str, scope: str) -> dict[str, Any]:
    store_id, binding = _resolve_store_id(browser_id, store_name)
    target_url = SCOPE_URLS.get(scope, HOME_URL)
    opened = cli_tools.ziniao_store_open(store_id, target_url)
    if not opened.get("ok"):
        raise RuntimeError(opened.get("summary") or "紫鸟店铺浏览器未能打开")
    visited = cli_tools.ziniao_page_visit(store_id, target_url, wait_until="domcontentloaded")
    if not visited.get("ok"):
        raise RuntimeError(visited.get("summary") or "紫鸟店铺浏览器未能导航到目标页面")
    content, text = _read_ready_page_content(store_id, scope)
    if not text:
        raise RuntimeError("Amazon 页面未返回可解析文本")
    low = text.lower()
    if any(marker in low for marker in ("sign in", "登录", "not a robot", "captcha", "人机验证", "验证码")):
        raise RuntimeError("Amazon 页面需要人工登录或完成验证")
    metrics = _account_health_metrics(text) if scope == "account_health" else _dashboard_metrics(text)
    if not metrics and not any(marker in low for marker in ("sellercentral.amazon.com", "seller central", "卖家", "我的业务", "账户状况")):
        raise RuntimeError("当前紫鸟店铺未处于可识别的 Seller Central 页面")
    return {
        "metrics": metrics,
        "products": [],
        "outbound_orders": [],
        "buyer_messages": [],
        "reviews": [],
        "cases": [],
        "page_url": target_url,
        "result_summary": {
            "products_count": 0,
            "orders_count": 0,
            "metrics_count": len(metrics),
            "transport": "zclaw",
            "store_binding": binding,
            "scope": scope,
        },
    }
