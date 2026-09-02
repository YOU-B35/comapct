"""Read-only Amazon Seller Central crawl through the official Ziniao ZClaw CLI."""
from __future__ import annotations

import json
import re
from typing import Any

from app.ziniao import cli_tools

HOME_URL = "https://sellercentral.amazon.com/amazonsell/business"


def _content_text(raw: Any) -> str:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return raw
    if not isinstance(raw, dict):
        return ""
    node: Any = raw
    for key in ("data", "data", "content"):
        if not isinstance(node, dict):
            break
        node = node.get(key)
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        return str(node.get("bodyText") or node.get("text") or node.get("content") or "")
    return ""


def _metric(label: str, text: str, pattern: str) -> dict[str, str] | None:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return {"metric_key": re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_"), "label": label, "value": match.group(1).strip(), "status": "normal"}


def _dashboard_metrics(text: str) -> list[dict[str, str]]:
    patterns = (
        ("today_sales", r"(?:今天到目前为止.{0,80}?已订购商品销售额|已订购商品销售额.{0,80}?今天到目前为止)\s*(US\$[\d,.]+)"),
        ("today_orders", r"(?:今天到目前为止.{0,80}?已订购商品数量|已订购商品数量.{0,80}?今天到目前为止)\s*([\d,]+)"),
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


def crawl_zclaw_amazon(*, browser_id: str, store_name: str, scope: str) -> dict[str, Any]:
    store_id, binding = _resolve_store_id(browser_id, store_name)
    opened = cli_tools.ziniao_store_open(store_id, HOME_URL)
    if not opened.get("ok"):
        raise RuntimeError(opened.get("summary") or "紫鸟店铺浏览器未能打开")
    content = cli_tools.ziniao_page_content(store_id)
    if not content.get("ok"):
        raise RuntimeError(content.get("summary") or "无法读取 Amazon 页面")
    text = _content_text(content.get("data"))
    if not text:
        raise RuntimeError("Amazon 页面未返回可解析文本")
    low = text.lower()
    if any(marker in low for marker in ("sign in", "登录", "not a robot", "captcha", "人机验证", "验证码")):
        raise RuntimeError("Amazon 页面需要人工登录或完成验证")
    metrics = _dashboard_metrics(text)
    if not metrics and "sellercentral.amazon.com" not in text.lower() and "卖家" not in text:
        raise RuntimeError("当前紫鸟店铺未处于可识别的 Seller Central 页面")
    return {
        "metrics": metrics,
        "products": [],
        "outbound_orders": [],
        "buyer_messages": [],
        "reviews": [],
        "cases": [],
        "page_url": HOME_URL,
        "result_summary": {"products_count": 0, "orders_count": 0, "metrics_count": len(metrics), "transport": "zclaw", "store_binding": binding},
    }
