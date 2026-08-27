"""orders-v3 分页爬取（直接按 URL 页码翻页，不再点击“下一页”）。"""
from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.amazon.page_urls import ORDER_LIST_SPECS
from app.amazon.parsers.seller_pages import EXTRACT_ORDERS_JS, parse_orders_from_text
from app.amazon.session_context import looks_login_page


_ORDER_SCROLL_JS = """
async () => {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  for (let i = 0; i < 8; i += 1) {
    window.scrollBy(0, 1200);
    await sleep(250);
  }
}
"""


def _order_page_url(url: str, page_index: int) -> str:
    """orders-v3 支持 URL 页码（?page=N）；直接跳转代替点击“下一页”。"""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["page"] = str(max(1, int(page_index) + 1))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def crawl_orders_v3(page, *, max_pages: int = 15) -> list[dict[str, Any]]:
    all_orders: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    def ingest(batch: list[dict[str, Any]], default_status: str, url: str) -> None:
        for row in batch:
            if not isinstance(row, dict):
                continue
            order_no = str(row.get("order_no") or "").strip()
            if not order_no or order_no in seen_keys:
                continue
            seen_keys.add(order_no)
            if not row.get("status") or row.get("status") == "pending":
                row["status"] = default_status
            if "/fba/" in url:
                row["fulfillment_type"] = "fba"
            elif "/mfn/" in url:
                row["fulfillment_type"] = "fbm"
            all_orders.append(row)

    for spec in ORDER_LIST_SPECS:
        url = spec["url"]
        default_status = spec["status"]
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            body = page.inner_text("body")
            if looks_login_page(body, page.url):
                continue
            page.evaluate(_ORDER_SCROLL_JS)
            page.wait_for_timeout(1200)

            for page_index in range(max_pages):
                batch = page.evaluate(EXTRACT_ORDERS_JS) or []
                if not isinstance(batch, list):
                    batch = []
                if not batch:
                    batch = parse_orders_from_text(body, default_status=default_status)
                if not batch:
                    break
                before = len(all_orders)
                ingest(batch, default_status, url)
                if len(all_orders) == before:
                    break

                # 直接用 URL 页码翻页（orders-v3 支持 ?page=N），不再点击“下一页”
                try:
                    page.goto(_order_page_url(url, page_index), wait_until="domcontentloaded")
                except Exception:
                    break
                page.wait_for_timeout(3000)
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                page.evaluate(_ORDER_SCROLL_JS)
                page.wait_for_timeout(1000)
                body = page.inner_text("body")
                if looks_login_page(body, page.url):
                    break
        except Exception:
            continue

    return all_orders
