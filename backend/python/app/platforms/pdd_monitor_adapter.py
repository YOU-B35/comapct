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
                config = _target_config(target)
                pinned = [str(x) for x in (config.get("pinned_offer_ids") or [])]
                strategy = str(target.get("crawl_strategy") or "pdd_shop_topn")
                if strategy == "pdd_pinned_offers":
                    goods_id = goods_id_from_url(target_url)
                    if goods_id and goods_id not in pinned:
                        pinned.insert(0, goods_id)
                products = collect_products(page, target_url, max_products, pinned_ids=pinned)
                products = ensure_pinned_products(page, target_url, products, pinned)
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


def _target_config(target: dict) -> dict[str, Any]:
    raw = target.get("config_json") or "{}"
    try:
        parsed = json.loads(str(raw))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def collect_products(
    page,
    base_url: str,
    max_products: int,
    *,
    pinned_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    pinned = {str(x) for x in (pinned_ids or [])}
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
        rows.append(to_product_row(
            product_id,
            href,
            text,
            base_url,
            len(rows) + 1,
            is_pinned=1 if product_id in pinned else 0,
        ))
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


def ensure_pinned_products(
    page,
    base_url: str,
    rows: list[dict[str, Any]],
    pinned: list[str],
) -> list[dict[str, Any]]:
    """盯梢商品即使不在店铺 Top N 列表也要进入快照（打开商品详情页补采）。"""
    existing = {str(r.get("product_id") or "") for r in rows}
    mall_id = mall_id_from_url(base_url)
    for goods_id in pinned:
        goods_id = str(goods_id or "").strip()
        if not goods_id or goods_id in existing:
            continue
        rows.append(collect_goods_detail(
            page,
            goods_id,
            mall_id=mall_id,
            base_url=base_url,
            rank=len(rows) + 1,
        ))
        existing.add(goods_id)
    return rows


def collect_goods_detail(
    page,
    goods_id: str,
    *,
    mall_id: str,
    base_url: str,
    rank: int,
) -> dict[str, Any]:
    """打开拼多多买家端商品详情页补采盯梢商品字段；失败时保留兜底行继续监控。"""
    url = f"https://mobile.yangkeduo.com/goods.html?goods_id={goods_id}"
    if mall_id:
        url += f"&mall_id={mall_id}"
    title = ""
    price = 0.0
    sales = 0
    expired = 0
    image_url = ""
    sale_text = ""
    body = ""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=PDD_MONITOR_NAV_TIMEOUT_MS)
        page.wait_for_timeout(1_200)
        body = safe_inner_text(page, "body")
        title = goods_page_title(page, body)
        price = first_number_after(body, ("¥", "￥"))
        sales = first_sales_number(body)
        sale_text = sales_text(body)
        if goods_page_expired(body):
            expired = 1
        image_url = goods_page_image(page)
    except Exception as exc:  # noqa: BLE001
        print(f"[PddMonitor] pinned goods={goods_id} detail parse failed: {exc}", flush=True)
    return to_product_row(
        goods_id,
        url,
        body,
        base_url,
        rank,
        is_pinned=1,
        status="onsale",
        expired=expired,
        title=title or goods_id,
        price=price,
        total_sales=sales,
        sale_text=sale_text,
        image_url=image_url,
    )


def to_product_row(
    product_id: str,
    href: str,
    text: str,
    base_url: str,
    rank: int,
    *,
    is_pinned: int = 0,
    status: str = "onsale",
    expired: int = 0,
    title: str | None = None,
    price: float | None = None,
    total_sales: int | None = None,
    sale_text: str | None = None,
    image_url: str = "",
) -> dict[str, Any]:
    price = first_number_after(text, ("¥", "￥")) if price is None else float(price)
    sales = first_sales_number(text) if total_sales is None else int(total_sales)
    title = clean_title(text) if title is None else collapse_text(title)
    sale_text = sales_text(text) if sale_text is None else collapse_text(sale_text)
    return {
        "product_id": product_id,
        "product_name": title or product_id,
        "category": "",
        "price": price,
        "daily_sales": 0,
        "total_sales": int(sales),
        "listed_at": "",
        "url": urljoin(base_url, href),
        "image_url": image_url,
        "shop_name": "",
        "shop_url": shop_url_from_url(base_url),
        "rank": rank,
        "price_range": "",
        "moq": "",
        "good_rate": "",
        "delivery_48h_rate": "",
        "sale_text": sale_text,
        "dropship_7d": "",
        "dropship_30d": "",
        "dropship_heat": 0,
        "rebuy_rate": "",
        "shop_return_rate": "",
        "quality_rate": "",
        "shop_fans": 0,
        "attrs_json": json.dumps(
            {"source": "pdd_dom", "is_pinned": is_pinned, "text": text[:500]},
            ensure_ascii=False,
        ),
        "is_pinned": is_pinned,
        "status": status,
        "expired": expired,
        "raw_json": json.dumps({"href": href, "text": text[:1000]}, ensure_ascii=False),
    }


def goods_id_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        return (parse_qs(parsed.query).get("goods_id") or [""])[0].strip()
    except Exception:
        return ""


def mall_id_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        return (parse_qs(parsed.query).get("mall_id") or [""])[0].strip()
    except Exception:
        return ""


def shop_url_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        mall_id = (parse_qs(parsed.query).get("mall_id") or [""])[0].strip()
        return f"https://mobile.yangkeduo.com/mall_page.html?mall_id={mall_id}" if mall_id else ""
    except Exception:
        return ""


def goods_page_title(page, body: str) -> str:
    """优先结构化节点取标题，回退到正文首行清洗结果。"""
    selectors = (
        "h1",
        "[class*='goods-name']",
        "[class*='goodsName']",
        "[class*='goods_name']",
        "[class*='title']",
    )
    for selector in selectors:
        try:
            value = collapse_text(str(page.inner_text(selector, timeout=1_000) or ""))
            if value:
                return value[:120]
        except Exception:
            pass
    try:
        meta = page.get_attribute("meta[property='og:title']", "content")
        value = collapse_text(str(meta or ""))
        if value:
            return value[:120]
    except Exception:
        pass
    return clean_title(body)


def goods_page_image(page) -> str:
    try:
        meta = page.get_attribute("meta[property='og:image']", "content")
        if meta:
            return str(meta).strip()
    except Exception:
        pass
    try:
        src = page.locator("img").first.get_attribute("src")
        return str(src or "").strip()
    except Exception:
        return ""


def goods_page_expired(body: str) -> bool:
    return any(
        marker in body
        for marker in (
            "商品已下架",
            "商品不存在",
            "该商品已失效",
            "商品已失效",
            "已失效或已下架",
            "不存在或已下架",
        )
    )


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
