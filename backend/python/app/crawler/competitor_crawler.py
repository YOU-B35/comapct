"""Temu competitor mall crawler via boards/ctf-website page-card pipeline."""
from __future__ import annotations

import os
import re
from datetime import date
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page

from app.browser.context import close_tenant_profile_browsers, human_pause
from app.config import is_headless, resolve_profile_dir
from app.external_snapshot.ctf_website import temu_competitor_analysis
from app.external_snapshot.ctf_website.temu_page_card_lib import (
    canonical_mall_url,
    collect_with_playwright,
    is_login_page,
    normalize_item,
    parse_mall_id,
)

PRICE_RE = re.compile(
    r"(?:US)?\$\s*([0-9]+(?:[,.][0-9]{3})*(?:\.[0-9]{1,2})?)"
    r"|(?:^|\s)R\s*([0-9]+(?:[,.][0-9]{3})*(?:\.[0-9]{1,2})?)"
    r"|[¥￥]\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)"
    r"|([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)\s*円",
    re.I,
)
SALES_RE = re.compile(
    r"([0-9]+(?:\.[0-9]+)?\s*[kKmM万]?)\s*(?:\+?\s*)?"
    r"(?:sold|已售|销量|人已买|件已售|orders?|販売)",
    re.I,
)
NOISE_LINES = {
    "free shipping",
    "almost sold out",
    "limited time",
    "today's deals",
}


def crawl_competitor_products(
    *,
    tenant_id: int,
    competitor_url: str,
    max_products: int = 80,
    crawl_date: str | None = None,
) -> dict:
    snapshot_date = crawl_date or date.today().isoformat()
    close_tenant_profile_browsers(tenant_id)
    try:
        snapshot = _collect_snapshot(tenant_id, competitor_url)
    except RuntimeError as exc:
        message = str(exc)
        if message.startswith("COMPETITOR_"):
            raise
        if is_browser_profile_error(message):
            close_tenant_profile_browsers(tenant_id)
            try:
                snapshot = _collect_snapshot(tenant_id, competitor_url)
            except Exception as retry_exc:
                raise _profile_unavailable_error(retry_exc) from retry_exc
        else:
            raise
    except Exception as exc:
        message = str(exc)
        if is_browser_profile_error(message):
            close_tenant_profile_browsers(tenant_id)
            try:
                snapshot = _collect_snapshot(tenant_id, competitor_url)
            except Exception as retry_exc:
                raise _profile_unavailable_error(retry_exc) from retry_exc
        else:
            raise RuntimeError(f"COMPETITOR_CRAWL_FAILED: {message or 'Competitor crawler failed'}") from exc

    status = snapshot.get("status", "NO_PRODUCTS")
    collection = snapshot.get("collection") or {}
    if status == "AUTH_REQUIRED" or is_login_page(str(collection.get("final_url") or ""), str(collection.get("page_title") or "")):
        raise RuntimeError(
            "COMPETITOR_FRONTEND_LOGIN_REQUIRED: Temu redirected to login. "
            "Run scripts/ctf-website/temu_mall_snapshot_pipeline.py with --interactive for this tenant profile, "
            "or complete buyer-side login in the tenant browser profile first."
        )
    if status != "OK" or not snapshot.get("raw_products"):
        raise RuntimeError(
            "COMPETITOR_NO_PRODUCTS: No competitor products were detected. "
            "Check mall_id, login state, or rerun with --interactive."
        )

    products = map_snapshot_products(snapshot["raw_products"], snapshot_date, max_products=max_products)
    if not products:
        raise RuntimeError(
            "COMPETITOR_NO_PRODUCTS: Page-card evidence was collected but no analyzable products remained."
        )
    return {
        "snapshot_date": snapshot_date,
        "url": competitor_url,
        "products": products,
        "raw_count": len(snapshot.get("raw_products") or []),
        "analysis": temu_competitor_analysis.analyze_products(
            snapshot["raw_products"],
            store_id=str(snapshot.get("target", {}).get("mall_id") or ""),
            latest_limit=min(max_products, 15),
            captured_at=snapshot.get("captured_at"),
        ),
    }


def _collect_snapshot(tenant_id: int, competitor_url: str) -> dict:
    store_url = _resolve_store_url(competitor_url)
    interactive = os.getenv("TEMU_COMPETITOR_INTERACTIVE", "").strip().lower() in ("1", "true", "yes")
    return collect_with_playwright(
        store_url,
        headless=is_headless(),
        scroll_rounds=int(os.getenv("TEMU_COMPETITOR_SCROLL_ROUNDS", "10")),
        wait_ms=int(os.getenv("TEMU_COMPETITOR_WAIT_MS", "1500")),
        user_data_dir=str(resolve_profile_dir(tenant_id)),
        use_default_profile=False,
        interactive=interactive,
        ready_timeout_ms=int(os.getenv("TEMU_COMPETITOR_READY_TIMEOUT_MS", "45000")),
    )


def _resolve_store_url(competitor_url: str) -> str:
    parsed = urlparse(competitor_url)
    if parse_qs(parsed.query).get("mall_id", [""])[0]:
        return canonical_mall_url(competitor_url)
    return competitor_url


def map_snapshot_products(raw_products: list[dict], crawl_date: str, *, max_products: int) -> list[dict]:
    products: list[dict] = []
    seen: set[str] = set()
    for raw in raw_products[:max_products]:
        normalized = normalize_item(raw)
        card = temu_competitor_analysis.normalize_card(
            {
                "goods_id": normalized.get("goods_id"),
                "goods_id_num": normalized.get("goods_id_num"),
                "title": normalized.get("title"),
                "title_clean": normalized.get("title_clean"),
                "href": normalized.get("href"),
                "price_yen": normalized.get("price_yen"),
                "sold_num": normalized.get("sold_num"),
                "sold_text": normalized.get("sold_text"),
                "rating": normalized.get("rating"),
                "reviews": normalized.get("reviews"),
            }
        )
        if not card:
            continue
        sales = card["sales"]["value"] or 0
        price = card["price"]["amount"] or 0.0
        product_id = card["product_id"]
        if product_id in seen:
            continue
        seen.add(product_id)
        products.append(
            {
                "product_id": product_id,
                "product_name": card["product_name"],
                "category": "",
                "price": float(price),
                "daily_sales": int(sales),
                "total_sales": int(sales),
                "listed_at": crawl_date,
                "url": card["product_url"],
            }
        )
    return products


def crawl_raw_products(tenant_id: int, competitor_url: str, *, max_products: int) -> list[dict]:
    snapshot = _collect_snapshot(tenant_id, competitor_url)
    return [
        {"text": item.get("text") or item.get("title") or "", "url": item.get("href") or ""}
        for item in (snapshot.get("raw_products") or [])[:max_products]
    ]


def extract_products_from_url(page: Page, url: str, *, max_products: int = 80) -> list[dict]:
    if is_temu_frontend_blocked(url):
        raise RuntimeError(
            "COMPETITOR_FRONTEND_LOGIN_REQUIRED: Temu frontend login or verification is required for this competitor URL."
        )
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    human_pause()
    ensure_accessible_competitor_page(page)
    try:
        page.wait_for_load_state("networkidle", timeout=20_000)
    except Exception:
        pass
    ensure_accessible_competitor_page(page)
    for _ in range(5):
        page.mouse.wheel(0, 900)
        human_pause()
        ensure_accessible_competitor_page(page)
    from app.external_snapshot.ctf_website.temu_page_card_lib import DOM_EXTRACT_JS

    items = page.evaluate(DOM_EXTRACT_JS) or []
    rows = []
    for item in items[:max_products]:
        rows.append({"text": item.get("text") or item.get("title") or "", "url": item.get("href") or ""})
    return rows


def normalize_products(raw_products: list[dict], crawl_date: str) -> list[dict]:
    products: list[dict] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_products, start=1):
        product = normalize_product(raw, fallback_index=index, crawl_date=crawl_date)
        if not product["product_name"]:
            continue
        key = product["product_id"]
        if key in seen:
            continue
        seen.add(key)
        products.append(product)
    return products


def normalize_product(raw: dict, *, fallback_index: int, crawl_date: str) -> dict:
    text = compact_text(raw.get("text", ""))
    url = raw.get("url", "") or raw.get("href", "")
    goods_id = product_id_from_url(url)
    if goods_id and goods_id.isdigit():
        normalized = normalize_item({"goods_id": goods_id, "href": url, "text": text, "title": text})
        card = temu_competitor_analysis.normalize_card(
            {
                "goods_id": normalized.get("goods_id"),
                "goods_id_num": normalized.get("goods_id_num"),
                "title": normalized.get("title"),
                "title_clean": normalized.get("title_clean"),
                "href": normalized.get("href"),
                "price_yen": normalized.get("price_yen"),
                "sold_num": normalized.get("sold_num"),
                "sold_text": normalized.get("sold_text"),
            }
        )
        if card:
            sales = card["sales"]["value"] or extract_sales_signal(text)
            price = card["price"]["amount"] or extract_price(text)
            return {
                "product_id": card["product_id"],
                "product_name": card["product_name"],
                "category": "",
                "price": float(price or 0),
                "daily_sales": int(sales or 0),
                "total_sales": int(sales or 0),
                "listed_at": crawl_date,
                "url": card["product_url"] or url,
            }
    product_id = goods_id or f"real_{fallback_index:04d}"
    return {
        "product_id": product_id,
        "product_name": extract_name(text, product_id),
        "category": "",
        "price": extract_price(text),
        "daily_sales": extract_sales_signal(text),
        "total_sales": extract_sales_signal(text),
        "listed_at": crawl_date,
        "url": url,
    }


def extract_price(text: str) -> float:
    match = PRICE_RE.search(text or "")
    if not match:
        return 0.0
    value = next((group for group in match.groups() if group), None)
    if not value:
        return 0.0
    return round(float(value.replace(",", "")), 2)


def extract_sales_signal(text: str) -> int:
    match = SALES_RE.search(text or "")
    if not match:
        return 0
    return parse_compact_number(match.group(1))


def parse_compact_number(value: str) -> int:
    raw = (value or "").strip().replace(",", "").replace(" ", "")
    if not raw:
        return 0
    multiplier = 1
    suffix = raw[-1].lower()
    if suffix == "k":
        multiplier = 1_000
        raw = raw[:-1]
    elif suffix == "m":
        multiplier = 1_000_000
        raw = raw[:-1]
    elif suffix == "万":
        multiplier = 10_000
        raw = raw[:-1]
    try:
        return int(float(raw) * multiplier)
    except ValueError:
        return 0


def is_temu_frontend_blocked(url: str) -> bool:
    normalized = (url or "").lower()
    return (
        "/login.html" in normalized
        or "login_scene=" in normalized
        or "bgn_verification" in normalized
        or "verification" in normalized
        or "challenge" in normalized
        or normalized.startswith("about:blank")
    )


def ensure_accessible_competitor_page(page: Page) -> None:
    if is_temu_frontend_blocked(page.url):
        raise RuntimeError(
            "COMPETITOR_FRONTEND_LOGIN_REQUIRED: Temu frontend login or verification is required for this competitor URL."
        )
    if page_contains_store_unavailable(page):
        raise RuntimeError("COMPETITOR_STORE_UNAVAILABLE: Temu reports this competitor store is unavailable.")


def is_browser_profile_error(message: str) -> bool:
    normalized = (message or "").lower()
    return (
        "target page, context or browser has been closed" in normalized
        or "user data directory is already in use" in normalized
        or "singletonlock" in normalized
        or "browser has been closed" in normalized
        or "chrome not reachable" in normalized
    )


def page_contains_store_unavailable(page: Page) -> bool:
    try:
        body = page.locator("body")
        if not body.count():
            return False
        text = body.inner_text(timeout=5_000).lower()
    except Exception:
        return False
    return (
        "this store is unavailable" in text
        or "store is unavailable" in text
        or "店铺不可用" in text
        or "該店鋪不可用" in text
    )


def compact_text(text: str) -> str:
    return "\n".join(line.strip() for line in re.split(r"[\r\n]+", text or "") if line.strip())


def extract_name(text: str, fallback: str) -> str:
    for line in compact_text(text).splitlines():
        normalized = line.strip()
        lowered = normalized.lower()
        if not normalized:
            continue
        if PRICE_RE.search(normalized) or SALES_RE.search(normalized):
            continue
        if lowered in NOISE_LINES:
            continue
        if len(normalized) <= 2:
            continue
        return normalized[:180]
    single_line_name = name_from_single_line(text)
    if single_line_name:
        return single_line_name[:180]
    return fallback


def name_from_single_line(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return ""
    price_match = PRICE_RE.search(normalized)
    sales_match = SALES_RE.search(normalized)
    cut_at = len(normalized)
    for match in (price_match, sales_match):
        if match:
            cut_at = min(cut_at, match.start())
    candidate = normalized[:cut_at].strip(" -|·")
    if len(candidate) <= 2:
        return ""
    return candidate


def product_id_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    query = parse_qs(parsed.query)
    for key in ("goods_id", "goodsId", "product_id", "productId", "sku_id", "skuId"):
        values = query.get(key)
        if values and values[0]:
            return values[0][:80]
    match = re.search(r"(?:goods|product|item|g|pd)[_/-]?([A-Za-z0-9]{6,})", parsed.path, re.I)
    if match:
        return match.group(1)[:80]
    match = re.search(r"-g-(\d+)\.html", parsed.path, re.I)
    if match:
        return match.group(1)
    return ""


def _profile_unavailable_error(exc: Exception) -> RuntimeError:
    message = str(exc)
    if message.startswith("COMPETITOR_"):
        return RuntimeError(message)
    if is_browser_profile_error(message):
        return RuntimeError(
            "COMPETITOR_BROWSER_PROFILE_UNAVAILABLE: Temu buyer-side browser profile could not be opened."
        )
    return RuntimeError(f"COMPETITOR_CRAWL_FAILED: {message or 'Competitor crawler failed'}")
