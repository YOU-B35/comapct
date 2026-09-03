"""Read-only Amazon Seller Central crawl through the official Ziniao CLI.

This is deliberately separate from the WebDriver pipeline. A Ziniao CLI store
id identifies a normal-mode profile, not a WebDriver ``browser_id``.
"""
from __future__ import annotations

from datetime import datetime
import os
import re
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.amazon.composer.product_composer import compose_product_rows, enrich_product_rows
from app.amazon.crawlers.account import parse_home_metrics, parse_home_news_and_cases
from app.amazon.page_urls import HEALTH_URL, INVENTORY_URLS, ORDER_LIST_SPECS, REPORT_URLS
from app.amazon.parsers.seller_pages import (
    EXTRACT_BUSINESS_REPORT_JS,
    EXTRACT_CATALOG_JS,
    EXTRACT_INVENTORY_JS,
    EXTRACT_ORDERS_JS,
    parse_inventory_cards_from_text,
    parse_orders_from_text,
)
from app.amazon.scope_planner import normalize_scope
from app.ziniao import cli_tools

HOME_URL = "https://sellercentral.amazon.com/amazonsell/business"
ZCLAW_SYNC_SCOPES = frozenset({"account_health", "daily", "reports"})


def _content_text(raw: Any) -> str:
    raw = cli_tools.decode_json_data(raw)
    if isinstance(raw, str):
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
        child = next(
            (node[key] for key in ("data", "content", "result", "value") if isinstance(node.get(key), (dict, str))),
            None,
        )
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
    parts = [str(item).strip() for item in node.get("headings") or [] if str(item).strip()]
    for item in (node.get("links") or []) + (node.get("buttons") or []):
        if isinstance(item, dict) and str(item.get("text") or "").strip():
            parts.append(str(item["text"]).strip())
    return "\n".join(parts)


def _metric(label: str, text: str, pattern: str) -> dict[str, str] | None:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return {
        "metric_key": re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_"),
        "label": label,
        "value": match.group(1).strip(),
        "status": "normal",
    }


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


def supports_zclaw_fast_scope(scope: str) -> bool:
    """Whether normal-mode CLI has a real extractor for this sync scope."""
    return normalize_scope(scope) in ZCLAW_SYNC_SCOPES


def _resolve_store_id(store_id: str, store_name: str) -> tuple[str, str]:
    if store_id:
        return store_id, "bound"
    listed = cli_tools.ziniao_store_list()
    if not listed.get("ok"):
        raise RuntimeError(listed.get("summary") or "无法读取紫鸟店铺列表")
    matches = [
        item for item in (listed.get("data") or [])
        if str(item.get("storeName") or "").strip() == store_name
        and any(marker in str(item.get("platformName") or "").lower() for marker in ("amazon", "亚马逊"))
    ]
    if len(matches) != 1:
        raise RuntimeError("当前账号未绑定紫鸟店铺，且无法按店铺名称唯一匹配 Amazon 店铺")
    matched_store_id = str(matches[0].get("storeId") or "").strip()
    if not matched_store_id:
        raise RuntimeError("紫鸟店铺列表未返回 storeId")
    return matched_store_id, "name_match"


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


def _page_content_ready(text: str) -> bool:
    low = text.lower()
    return bool(text.strip()) and not any(marker in low for marker in ("正在加载", "loading...", "loading…", "please wait"))


def _read_ready_page_content(store_id: str) -> str:
    last_result: dict[str, Any] = {}
    last_text = ""
    attempts = _content_retry_count()
    for attempt in range(attempts):
        result = cli_tools.ziniao_page_content(store_id)
        last_result = result
        if result.get("ok"):
            last_text = _content_text(result.get("data"))
            if _page_content_ready(last_text):
                return last_text
        if attempt < attempts - 1:
            time.sleep(_content_retry_delay())
    if not last_result.get("ok"):
        raise RuntimeError(last_result.get("summary") or "无法读取 Amazon 页面")
    return last_text


def _ensure_seller_page(text: str) -> None:
    low = text.lower()
    if any(marker in low for marker in ("sign in", "登录", "not a robot", "captcha", "人机验证", "验证码")):
        raise RuntimeError("Amazon 页面需要人工登录或完成验证")
    if not any(marker in low for marker in ("sellercentral.amazon.com", "seller central", "卖家", "我的业务", "账户状况", "订单")):
        raise RuntimeError("当前紫鸟店铺未处于可识别的 Seller Central 页面")


def _visit_and_read(store_id: str, url: str) -> str:
    visited = cli_tools.ziniao_page_visit(store_id, url, wait_until="domcontentloaded")
    if not visited.get("ok"):
        raise RuntimeError(visited.get("summary") or "紫鸟店铺浏览器未能导航到目标页面")
    text = _read_ready_page_content(store_id)
    _ensure_seller_page(text)
    return text


def _unwrap_exec_value(value: Any) -> Any:
    value = cli_tools.decode_json_data(value)
    for _ in range(3):
        if not isinstance(value, dict):
            break
        child = next((value[key] for key in ("result", "value", "data") if key in value), None)
        if child is None:
            break
        value = cli_tools.decode_json_data(child)
    return value


def _exec_rows(store_id: str, js: str) -> list[dict[str, Any]]:
    result = cli_tools.ziniao_page_exec(store_id, js)
    if not result.get("ok"):
        raise RuntimeError(result.get("summary") or "紫鸟 CLI 页面脚本执行失败")
    value = _unwrap_exec_value(result.get("data"))
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _merge_metrics(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for rows in groups:
        for row in rows:
            key = str(row.get("metric_key") or "").strip()
            if key:
                merged[key] = row
    return list(merged.values())


def _order_page_url(url: str, page_index: int) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["page"] = str(max(1, page_index + 1))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _zclaw_order_pages() -> int:
    try:
        return max(1, min(int(os.environ.get("AMAZON_ZCLAW_ORDER_MAX_PAGES", "5")), 15))
    except ValueError:
        return 5


def _crawl_orders(store_id: str) -> list[dict[str, Any]]:
    all_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for spec in ORDER_LIST_SPECS:
        for page_index in range(_zclaw_order_pages()):
            text = _visit_and_read(store_id, _order_page_url(spec["url"], page_index))
            rows = _exec_rows(store_id, EXTRACT_ORDERS_JS) or parse_orders_from_text(text, default_status=spec["status"])
            if not rows:
                break
            added = 0
            for row in rows:
                order_no = str(row.get("order_no") or "").strip()
                if not order_no or order_no in seen:
                    continue
                seen.add(order_no)
                row.setdefault("status", spec["status"])
                if "/fba/" in spec["url"]:
                    row["fulfillment_type"] = "fba"
                elif "/mfn/" in spec["url"]:
                    row["fulfillment_type"] = "fbm"
                all_rows.append(row)
                added += 1
            if not added:
                break
    return all_rows


def _crawl_products(store_id: str) -> list[dict[str, Any]]:
    report_text = _visit_and_read(store_id, REPORT_URLS[0])
    report_rows = _exec_rows(store_id, EXTRACT_BUSINESS_REPORT_JS) or _exec_rows(store_id, EXTRACT_CATALOG_JS)
    inventory_text = _visit_and_read(store_id, INVENTORY_URLS[0])
    inventory_rows = _exec_rows(store_id, EXTRACT_INVENTORY_JS) or _exec_rows(store_id, EXTRACT_CATALOG_JS)
    if not inventory_rows:
        inventory_rows = parse_inventory_cards_from_text(inventory_text)
    products = compose_product_rows(report_rows, inventory_rows, [])
    if not products and report_text:
        products = compose_product_rows([], parse_inventory_cards_from_text(report_text), inventory_rows)
    return enrich_product_rows(products)


def _empty_result() -> dict[str, Any]:
    return {
        "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "metrics": [], "products": [], "outbound_orders": [], "buyer_messages": [],
        "reviews": [], "coupons": [], "seller_news": [], "shipments": [], "cases": [],
        "page_url": "", "page_diagnostics": [], "result_summary": {},
    }


def crawl_zclaw_amazon(*, store_id: str = "", store_name: str, scope: str) -> dict[str, Any]:
    normalized_scope = normalize_scope(scope)
    if not supports_zclaw_fast_scope(normalized_scope):
        raise RuntimeError(f"ZClaw 暂不支持 {normalized_scope or 'unknown'} 的同步范围")
    store_id, binding = _resolve_store_id(store_id, store_name)
    target_url = HEALTH_URL if normalized_scope == "account_health" else HOME_URL
    opened = cli_tools.ziniao_store_open(store_id, target_url)
    if not opened.get("ok"):
        raise RuntimeError(opened.get("summary") or "紫鸟店铺浏览器未能打开")

    result = _empty_result()
    if normalized_scope == "account_health":
        health_text = _visit_and_read(store_id, HEALTH_URL)
        result["page_url"] = HEALTH_URL
        result["metrics"] = _merge_metrics(_account_health_metrics(health_text), parse_home_metrics(health_text))
        if not result["metrics"]:
            raise RuntimeError("ZClaw 未从账户状况页面解析到指标")
    else:
        home_text = _visit_and_read(store_id, HOME_URL)
        result["page_url"] = HOME_URL
        result["metrics"] = _merge_metrics(_dashboard_metrics(home_text), parse_home_metrics(home_text))
        result["seller_news"], result["cases"] = parse_home_news_and_cases(home_text)
    if normalized_scope == "daily":
        result["outbound_orders"] = _crawl_orders(store_id)
        if not result["metrics"] and not result["outbound_orders"]:
            raise RuntimeError("ZClaw 未从今日运营页面解析到指标或订单")
    elif normalized_scope == "reports":
        result["products"] = _crawl_products(store_id)
        result["page_url"] = REPORT_URLS[0]
        if not result["products"]:
            raise RuntimeError("ZClaw 未从 Business Report 或库存页面解析到商品明细")

    result["result_summary"] = {
        "products_count": len(result["products"]),
        "orders_count": len(result["outbound_orders"]),
        "metrics_count": len(result["metrics"]),
        "transport": "zclaw", "store_binding": binding, "scope": normalized_scope, "complete": True,
    }
    return result
