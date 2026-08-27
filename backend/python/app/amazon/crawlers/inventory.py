"""库存 / 目录爬取。"""
from __future__ import annotations

import re

from typing import Any

from app.amazon.composer.product_filters import filter_valid_product_rows
from app.amazon.composer.product_composer import merge_product_catalog
from app.amazon.crawlers._page_js import evaluate_js
from app.amazon.page_urls import CATALOG_URLS, INVENTORY_URLS, REPORT_URLS
from app.amazon.parsers.seller_pages import (
    EXTRACT_BUSINESS_REPORT_JS,
    EXTRACT_CATALOG_JS,
    EXTRACT_INVENTORY_CARDS_JS,
    EXTRACT_INVENTORY_JS,
    EXTRACT_MYINVENTORY_GRID_JS,
    parse_inventory_cards_from_text,
)
from app.amazon.session_context import looks_login_page, save_capture

_LISTING_ID_RE = re.compile(r"^[A-Z0-9]{10}$", re.I)


def _listing_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        asin = str(row.get("asin") or "").strip().upper()
        if _LISTING_ID_RE.match(asin):
            kept.append(row)
    return kept


def _click_report_apply(page) -> None:
    try:
        page.evaluate(
            """
            () => {
              const nodes = [...document.querySelectorAll('button, kat-button, input[type=submit]')];
              const btn = nodes.find((node) => /apply|应用|run report|刷新|更新|generate/i.test(
                (node.innerText || node.value || '').trim()
              ));
              if (btn) btn.click();
            }
            """
        )
        page.wait_for_timeout(6000)
    except Exception:
        pass


def crawl_inventory_for_asins(
    page,
    asins: list[str],
    *,
    store_name: str = "",
    max_asins: int = 30,
) -> list[dict[str, Any]]:
    """在 Manage Inventory 搜索框按 ASIN 补抓 FBA Available。"""
    if not asins:
        return []
    targets = [str(a).strip().upper() for a in asins if str(a).strip()][:max_asins]
    if not targets:
        return []

    try:
        page.goto(INVENTORY_URLS[0], wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    search_selectors = (
        'input[placeholder*="ASIN"]',
        'input[placeholder*="asin"]',
        'input[type="search"]',
        'input[aria-label*="Search"]',
    )
    for asin in targets:
        if asin in seen:
            continue
        try:
            filled = False
            for sel in search_selectors:
                loc = page.locator(sel).first
                if loc.count() == 0:
                    continue
                loc.click(timeout=3000)
                loc.fill(asin, timeout=3000)
                loc.press("Enter")
                filled = True
                break
            if not filled:
                page.evaluate(
                    """
                    (asin) => {
                      const inputs = [...document.querySelectorAll('input')];
                      const box = inputs.find((el) => /asin|search|sku|title/i.test(
                        (el.getAttribute('placeholder') || el.getAttribute('aria-label') || '').trim()
                      ));
                      if (!box) return false;
                      box.focus();
                      box.value = asin;
                      box.dispatchEvent(new Event('input', { bubbles: true }));
                      box.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
                      return true;
                    }
                    """,
                    asin,
                )
            page.wait_for_timeout(2500)
            found = evaluate_js(page, EXTRACT_MYINVENTORY_GRID_JS)
            if not found:
                found = parse_inventory_cards_from_text(page.inner_text("body"))
            match = next((row for row in found or [] if str(row.get("asin") or "").upper() == asin), None)
            if match:
                seen.add(asin)
                rows.append(match)
        except Exception:
            continue
    return _listing_rows(rows)


def crawl_inventory_products(
    page,
    *,
    store_name: str = "",
    max_pages: int = 3,
    fast: bool = False,
) -> list[dict[str, Any]]:
    inventory_urls = INVENTORY_URLS[:1] if fast else INVENTORY_URLS
    initial_wait = 5000 if fast else 10000
    follow_wait = 4000 if fast else 8000
    network_idle_timeout = 6000 if fast else 8000
    scroll_wait = 800 if fast else 1000
    page_wait = 1500 if fast else 2000
    for url_index, url in enumerate(inventory_urls):
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(follow_wait if url_index else initial_wait)
            try:
                page.wait_for_load_state("networkidle", timeout=network_idle_timeout)
            except Exception:
                pass
            all_rows: list[dict[str, Any]] = []
            seen_asins: set[str] = set()
            for _ in range(max_pages):
                page.evaluate("() => { window.scrollTo(0, document.body.scrollHeight); }")
                page.wait_for_timeout(scroll_wait)
                body = page.inner_text("body")
                if looks_login_page(body, page.url):
                    break
                rows = evaluate_js(page, EXTRACT_MYINVENTORY_GRID_JS) if "myinventory" in (page.url or "") else []
                if not rows:
                    rows = evaluate_js(page, EXTRACT_INVENTORY_CARDS_JS)
                if not rows:
                    rows = parse_inventory_cards_from_text(body)
                table_rows = evaluate_js(page, EXTRACT_INVENTORY_JS)
                if table_rows:
                    by_asin = {str(r.get("asin") or "").upper(): r for r in rows if r.get("asin")}
                    for tr in table_rows:
                        asin = str(tr.get("asin") or "").upper()
                        if not asin:
                            continue
                        inv = str(tr.get("inventory") or "0")
                        if asin in by_asin:
                            if int(inv or 0) > int(str(by_asin[asin].get("inventory") or "0")):
                                by_asin[asin]["inventory"] = inv
                        else:
                            by_asin[asin] = tr
                    rows = list(by_asin.values())
                if not rows:
                    rows = table_rows or []
                if not rows:
                    rows = evaluate_js(page, EXTRACT_CATALOG_JS)
                for row in rows or []:
                    if not isinstance(row, dict):
                        continue
                    asin = str(row.get("asin") or "").strip().upper()
                    if not asin or asin in seen_asins:
                        continue
                    seen_asins.add(asin)
                    all_rows.append(row)
                clicked = page.evaluate(
                    """
                    () => {
                      const btn = [...document.querySelectorAll('button, a, kat-pagination button')].find((el) =>
                        /next|下一页|›|→|>>/i.test((el.innerText || el.getAttribute('aria-label') || '').trim())
                      );
                      if (!btn || btn.disabled || btn.getAttribute('aria-disabled') === 'true') return false;
                      btn.click();
                      return true;
                    }
                    """
                )
                if not clicked:
                    break
                page.wait_for_timeout(page_wait)
            listing_rows = _listing_rows(all_rows)
            valid = filter_valid_product_rows(listing_rows)
            if valid:
                return listing_rows or valid
            if listing_rows:
                return listing_rows
            if fast and (valid or listing_rows or all_rows):
                return listing_rows or all_rows
            if all_rows and url_index >= len(inventory_urls) - 1:
                save_capture(page, store_name=store_name, suffix="inv_invalid")
        except Exception:
            continue
    return []


def crawl_catalog_products(page, *, store_name: str = "") -> list[dict[str, Any]]:
    for url in CATALOG_URLS:
        try:
            page.goto(url, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=25000)
            except Exception:
                pass
            if url in REPORT_URLS:
                _click_report_apply(page)
            page.wait_for_timeout(5000)
            page.evaluate("() => { window.scrollTo(0, document.body.scrollHeight); }")
            page.wait_for_timeout(1500)
            body = page.inner_text("body")
            if looks_login_page(body, page.url):
                continue
            rows = evaluate_js(page, EXTRACT_CATALOG_JS)
            if not rows and url in REPORT_URLS:
                rows = evaluate_js(page, EXTRACT_BUSINESS_REPORT_JS)
            valid = filter_valid_product_rows(rows)
            if valid:
                return valid
            if rows:
                save_capture(page, store_name=store_name, suffix="catalog_invalid")
        except Exception:
            continue
    return []


def crawl_home_catalog(page) -> list[dict[str, Any]]:
    try:
        return filter_valid_product_rows(evaluate_js(page, EXTRACT_CATALOG_JS))
    except Exception:
        return []


def merge_catalog_sources(
    inventory_rows: list[dict[str, Any]],
    home_rows: list[dict[str, Any]],
    *,
    store_name: str = "",
    page=None,
) -> list[dict[str, Any]]:
    merged = merge_product_catalog(inventory_rows, home_rows)
    if page is not None and len(merged) < 18:
        extra = crawl_catalog_products(page, store_name=store_name)
        merged = merge_product_catalog(merged, extra)
    return merged
