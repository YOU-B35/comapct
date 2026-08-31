"""PDD buyer-side monitor adapter."""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from app.platforms.base import MonitorPlatformAdapter


def _env_int(name: str, default: int, minimum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


PDD_MONITOR_NAV_TIMEOUT_MS = _env_int("PDD_MONITOR_NAV_TIMEOUT_MS", 45_000, 15_000)
PDD_MONITOR_READY_TIMEOUT_MS = _env_int("PDD_MONITOR_READY_TIMEOUT_MS", 8_000, 2_000)
PDD_MONITOR_SCROLL_ROUNDS = _env_int("PDD_MONITOR_SCROLL_ROUNDS", 3, 0)


class PddMonitorAdapter(MonitorPlatformAdapter):
    def crawl_target(self, *, tenant_id: int, target: dict, max_products: int) -> dict[str, Any]:
        from agent.pdd_tasks import _close_pw, _launch, _run_in_clean_thread

        def _run() -> dict[str, Any]:
            pw = context = page = None
            try:
                store_id = str(target.get("store_id") or "buyer").strip() or "buyer"
                pw, context, page = _launch(
                    tenant_id,
                    headless=False,
                    force_navigate=False,
                    store_id=store_id,
                )
                target_url = str(target.get("target_url") or "").strip()
                if not target_url:
                    raise RuntimeError("PDD_PRODUCTS_SOURCE_UNAVAILABLE: target_url is empty")
                started = time.perf_counter()
                page.goto(target_url, wait_until="domcontentloaded", timeout=PDD_MONITOR_NAV_TIMEOUT_MS)
                wait_for_product_links(page, timeout_ms=PDD_MONITOR_READY_TIMEOUT_MS)
                scroll_for_lazy_products(page, max_products=max_products)
                products = collect_products(page, target_url, max_products)
                if not products:
                    body = safe_inner_text(page, "body")
                    if looks_auth_required(page.url, body):
                        raise RuntimeError("PDD_NOT_LOGGED_IN: 拼多多买家态未登录或登录已失效")
                    raise RuntimeError("PDD_PRODUCTS_SOURCE_UNAVAILABLE: 未能从拼多多页面提取商品数据")
                print(
                    f"[PddPerf] monitor_dom target_products={len(products)} "
                    f"elapsed={time.perf_counter() - started:.2f}s",
                    flush=True,
                )
                return {
                    "platform": "pdd",
                    "snapshot_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "products": products,
                }
            finally:
                _close_pw(pw, context)

        return _run_in_clean_thread(_run, timeout=240)


def collect_products(page, base_url: str, max_products: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        page.wait_for_selector("a[href*='goods.html'], a[href*='goods_id=']", timeout=5_000)
        handles = page.locator("a[href*='goods.html'], a[href*='goods_id=']").element_handles()
    except Exception:
        handles = []
    for handle in handles:
        if len(rows) >= max_products:
            break
        href = safe_attr(handle, "href")
        product_id = goods_id_from_url(href)
        if not product_id or product_id in seen:
            continue
        seen.add(product_id)
        text = collapse_text(safe_text(handle))
        if not text:
            parent = handle.evaluate(
                """(node) => {
                    const p = node.closest('div,li,section') || node.parentElement;
                    return p ? p.innerText : '';
                }"""
            )
            text = collapse_text(str(parent or ""))
        rows.append(to_product_row(product_id, href, text, base_url, len(rows) + 1))
    return rows


def wait_for_product_links(page, *, timeout_ms: int) -> bool:
    try:
        page.wait_for_selector("a[href*='goods.html'], a[href*='goods_id=']", timeout=timeout_ms)
        return True
    except Exception:
        return False


def scroll_for_lazy_products(page, *, max_products: int) -> None:
    selector = "a[href*='goods.html'], a[href*='goods_id=']"
    for _ in range(PDD_MONITOR_SCROLL_ROUNDS):
        try:
            if page.locator(selector).count() >= max_products:
                return
        except Exception:
            pass
        try:
            page.evaluate("window.scrollBy(0, Math.max(600, window.innerHeight || 600))")
            page.wait_for_timeout(400)
        except Exception:
            return


def to_product_row(product_id: str, href: str, text: str, base_url: str, rank: int) -> dict[str, Any]:
    price = first_number_after(text, ("¥", "￥"))
    sales = first_sales_number(text)
    title = clean_title(text)
    return {
        "product_id": product_id,
        "product_name": title or product_id,
        "category": "",
        "price": price,
        "daily_sales": 0,
        "total_sales": sales,
        "listed_at": "",
        "url": urljoin(base_url, href),
        "image_url": "",
        "shop_name": "",
        "shop_url": shop_url_from_url(base_url),
        "rank": rank,
        "price_range": "",
        "moq": "",
        "good_rate": "",
        "delivery_48h_rate": "",
        "sale_text": sales_text(text),
        "dropship_7d": "",
        "dropship_30d": "",
        "dropship_heat": 0,
        "rebuy_rate": "",
        "shop_return_rate": "",
        "quality_rate": "",
        "shop_fans": 0,
        "attrs_json": json.dumps({"source": "pdd_dom", "text": text[:500]}, ensure_ascii=False),
        "is_pinned": 0,
        "status": "onsale",
        "expired": 0,
        "raw_json": json.dumps({"href": href, "text": text[:1000]}, ensure_ascii=False),
    }


def goods_id_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        return (parse_qs(parsed.query).get("goods_id") or [""])[0].strip()
    except Exception:
        return ""


def shop_url_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        mall_id = (parse_qs(parsed.query).get("mall_id") or [""])[0].strip()
        return f"https://mobile.yangkeduo.com/mall_page.html?mall_id={mall_id}" if mall_id else ""
    except Exception:
        return ""


def first_number_after(text: str, markers: tuple[str, ...]) -> float:
    for marker in markers:
        idx = text.find(marker)
        if idx >= 0:
            match = re.search(r"\d+(?:\.\d+)?", text[idx:idx + 24])
            if match:
                return float(match.group(0))
    return 0.0


def first_sales_number(text: str) -> int:
    match = re.search(r"(\d+(?:\.\d+)?)(万)?\s*(?:人已拼|已拼|件|销量|售)", text)
    if not match:
        return 0
    value = float(match.group(1))
    if match.group(2):
        value *= 10_000
    return int(value)


def sales_text(text: str) -> str:
    match = re.search(r"\d+(?:\.\d+)?万?\s*(?:人已拼|已拼|件|销量|售)", text)
    return match.group(0) if match else ""


def clean_title(text: str) -> str:
    cleaned = re.sub(r"[¥￥]\s*\d+(?:\.\d+)?", " ", text)
    cleaned = re.sub(r"\d+(?:\.\d+)?万?\s*(?:人已拼|已拼|件|销量|售)", " ", cleaned)
    cleaned = collapse_text(cleaned)
    return cleaned[:120]


def collapse_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def looks_auth_required(url: str, body: str) -> bool:
    lower_url = str(url or "").lower()
    return "login" in lower_url or "passport" in lower_url or any(
        marker in body for marker in ("登录", "验证码", "请先登录", "安全验证")
    )


def safe_inner_text(page, selector: str) -> str:
    try:
        return str(page.inner_text(selector, timeout=3_000) or "")
    except Exception:
        return ""


def safe_text(handle) -> str:
    try:
        return str(handle.inner_text(timeout=2_000) or "")
    except Exception:
        return ""


def safe_attr(handle, name: str) -> str:
    try:
        return str(handle.get_attribute(name) or "")
    except Exception:
        return ""
