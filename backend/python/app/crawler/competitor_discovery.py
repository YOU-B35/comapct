"""Discover crawlable Temu competitor candidates from front-end search pages."""
from __future__ import annotations

from collections import OrderedDict
import re
import time
from urllib.parse import parse_qs, quote, urlparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from app.browser.context import close_temu_runtime, close_tenant_profile_browsers, get_or_create_temu_runtime, human_pause
from app.browser.manual_chrome import frontend_login_required_error, open_manual_frontend_chrome
from app.crawler.competitor_crawler import (
    extract_name,
    extract_price,
    extract_sales_signal,
    is_browser_profile_error,
    is_temu_frontend_blocked,
    page_contains_store_unavailable,
)

DEFAULT_DISCOVERY_KEYWORD = "fishing tackle"
DEFAULT_DISCOVERY_REGION = "za"
DEFAULT_DISCOVERY_LIMIT = 10
PROFILE_SETTLE_SECONDS = 2.0
PROFILE_RETRY_ATTEMPTS = 2
PRODUCT_URL_RE = re.compile(r"(goods|product|item|sku|_oak|[/_\-]g-\d|pd-\d|goods_id=)", re.I)


def build_search_url(keyword: str = DEFAULT_DISCOVERY_KEYWORD, region: str = DEFAULT_DISCOVERY_REGION) -> str:
    normalized_region = (region or DEFAULT_DISCOVERY_REGION).strip().strip("/") or DEFAULT_DISCOVERY_REGION
    normalized_keyword = (keyword or DEFAULT_DISCOVERY_KEYWORD).strip() or DEFAULT_DISCOVERY_KEYWORD
    return f"https://www.temu.com/{normalized_region}/search_result.html?search_key={quote(normalized_keyword)}"


def discover_competitor_candidates(
    *,
    tenant_id: int,
    keyword: str = DEFAULT_DISCOVERY_KEYWORD,
    region: str = DEFAULT_DISCOVERY_REGION,
    limit: int = DEFAULT_DISCOVERY_LIMIT,
) -> dict:
    search_url = build_search_url(keyword, region)
    try:
        items = discover_raw_items(tenant_id, search_url, max_items=max(limit * 4, 24))
    except RuntimeError as exc:
        message = str(exc)
        if message.startswith("COMPETITOR_"):
            raise
        if is_browser_profile_error(message):
            items = retry_discovery_after_closing_profile(tenant_id, search_url, max_items=max(limit * 4, 24), original=exc)
        else:
            raise RuntimeError(f"COMPETITOR_CRAWL_FAILED: {message or 'Competitor discovery failed'}") from exc
    except Exception as exc:
        message = str(exc)
        if is_browser_profile_error(message):
            items = retry_discovery_after_closing_profile(tenant_id, search_url, max_items=max(limit * 4, 24), original=exc)
        else:
            raise RuntimeError(f"COMPETITOR_CRAWL_FAILED: {message or 'Competitor discovery failed'}") from exc

    candidates = build_discovery_candidates(items, search_url=search_url, keyword=keyword, limit=limit)
    if not candidates:
        raise RuntimeError(
            f"COMPETITOR_DISCOVERY_NO_RESULTS: No candidates were found for "
            f"{keyword!r} on Temu {region.upper()}. Try again later or use a manual competitor URL."
        )
    return {
        "keyword": keyword,
        "region": region,
        "searchUrl": search_url,
        "candidates": candidates,
    }


def discover_raw_items(tenant_id: int, search_url: str, *, max_items: int) -> list[dict]:
    runtime = get_or_create_temu_runtime(tenant_id, headless=False)
    page = runtime.context.new_page()
    try:
        return extract_search_items_from_url(page, search_url, max_items=max_items)
    except RuntimeError as exc:
        message = str(exc)
        if message.startswith("COMPETITOR_FRONTEND_LOGIN_REQUIRED") or message.startswith("COMPETITOR_LOGIN_REQUIRED"):
            # Playwright login.html is often blank; release profile and open real Chrome.
            try:
                page.close()
            except Exception:
                pass
            opened = open_manual_frontend_chrome(tenant_id, search_url or "https://www.temu.com/")
            raise frontend_login_required_error(opened) from exc
        raise
    finally:
        try:
            closed = page.is_closed() if hasattr(page, "is_closed") else getattr(page, "closed", False)
            if not closed:
                page.close()
        except Exception:
            pass


def retry_discovery_after_closing_profile(tenant_id: int, search_url: str, *, max_items: int, original: Exception) -> list[dict]:
    last_exc: Exception = original
    for attempt in range(PROFILE_RETRY_ATTEMPTS):
        close_temu_runtime(tenant_id)
        close_tenant_profile_browsers(tenant_id)
        time.sleep(PROFILE_SETTLE_SECONDS)
        try:
            return discover_raw_items(tenant_id, search_url, max_items=max_items)
        except Exception as exc:
            last_exc = exc
            message = str(exc)
            if message.startswith("COMPETITOR_"):
                raise
            if not is_browser_profile_error(message):
                raise RuntimeError(f"COMPETITOR_CRAWL_FAILED: {message or str(original) or 'Competitor discovery failed'}") from exc
            if attempt == PROFILE_RETRY_ATTEMPTS - 1:
                raise RuntimeError(
                    "COMPETITOR_BROWSER_PROFILE_UNAVAILABLE: Temu buyer-side browser profile could not be opened after force-closing tenant browser windows."
                ) from exc
    raise RuntimeError(f"COMPETITOR_CRAWL_FAILED: {str(last_exc) or str(original) or 'Competitor discovery failed'}")


def extract_search_items_from_url(page: Page, url: str, *, max_items: int = 40) -> list[dict]:
    if is_temu_frontend_blocked(url):
        raise RuntimeError(
            "COMPETITOR_FRONTEND_LOGIN_REQUIRED: Temu frontend login or verification is required before discovering competitors."
        )
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=35_000)
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(
            "COMPETITOR_NAVIGATION_TIMEOUT: Timed out opening the Temu discovery search page."
        ) from exc
    human_pause()
    # Temu may bounce to login.html with a blank body under Playwright automation.
    ensure_discovery_page_accessible(page)
    try:
        page.wait_for_load_state("networkidle", timeout=8_000)
    except Exception:
        pass
    ensure_discovery_page_accessible(page)

    for _ in range(2):
        page.mouse.wheel(0, 900)
        human_pause()
        ensure_discovery_page_accessible(page)

    # Temu 搜索页是强动态的：首次抽取可能为空，此时额外滚动并重试抽取。
    rows = extract_search_items_from_page(page, max_items=max_items)
    if rows:
        return rows

    for _ in range(2):
        page.mouse.wheel(0, 900)
        human_pause()
        ensure_discovery_page_accessible(page)
        rows = extract_search_items_from_page(page, max_items=max_items)
        if rows:
            return rows

    # 兜底：严格抽取可能因为前端文案/价格格式变化过于保守，改用宽松抽取策略。
    if not rows:
        rows = extract_search_items_from_page_lenient(page, max_items=max_items)
    return rows


def ensure_discovery_page_accessible(page: Page) -> None:
    if is_temu_frontend_blocked(page.url) or page_looks_like_blank_frontend_login(page):
        raise RuntimeError(
            "COMPETITOR_FRONTEND_LOGIN_REQUIRED: Temu frontend login or verification is required before discovering competitors."
        )
    if page_contains_store_unavailable(page):
        raise RuntimeError("COMPETITOR_STORE_UNAVAILABLE: Temu reports this discovery page is unavailable in the current region/session.")


def page_looks_like_blank_frontend_login(page: Page) -> bool:
    """Detect Playwright blank Temu buyer login (title often ログイン / Login)."""
    url = (page.url or "").lower()
    if is_temu_frontend_blocked(url):
        return True
    title = ""
    try:
        title = (page.title() or "").strip()
    except Exception:
        title = ""
    title_l = title.lower()
    loginish = (
        "login" in title_l
        or "ログイン" in title
        or "로그인" in title
        or "登录" in title
    )
    if not loginish and "about:blank" not in url:
        return False
    text = ""
    try:
        body = page.locator("body")
        if body.count():
            text = (body.inner_text(timeout=2_000) or "").strip()
    except Exception:
        text = ""
    return len(text) < 40


def extract_search_items_from_page(page: Page, *, max_items: int = 40) -> list[dict]:
    return page.evaluate(
        """
        ({ maxItems }) => {
          const anchors = Array.from(document.querySelectorAll('a[href]'));
          const seen = new Set();
          const rows = [];
          const productHints = /(goods|product|item|sku|_oak|\\bg-\\d|\\bpd-\\d)/i;
          const pricePattern = /(?:US)?\\$\\s*\\d|(?:^|\\s)R\\s*\\d|[¥￥]\\s*\\d|\\d[\\d,]*\\s*円/i;
          const textOf = (node) => ((node && (node.innerText || node.textContent)) || '')
            .replace(/[ \\t]+/g, ' ')
            .trim();
          const cardTextFor = (anchor) => {
            let node = anchor;
            let best = textOf(anchor);
            for (let depth = 0; node && depth < 7; depth += 1) {
              const current = textOf(node);
              if (current && pricePattern.test(current) && current.length >= best.length) {
                return current;
              }
              if (current.length > best.length && current.length < 1200) best = current;
              node = node.parentElement;
            }
            return best;
          };
          const mallLinkFor = (anchor) => {
            let node = anchor;
            for (let depth = 0; node && depth < 7; depth += 1) {
              const mallLink = node.querySelector && node.querySelector('a[href*="mall_id"], a[href*="mall.html"]');
              if (mallLink && mallLink.href) return mallLink.href;
              node = node.parentElement;
            }
            return '';
          };
          for (const anchor of anchors) {
            const href = anchor.href || anchor.getAttribute('href') || '';
            const cardText = cardTextFor(anchor);
            if (!href || seen.has(href)) continue;
            if (!productHints.test(href) && !pricePattern.test(cardText)) continue;
            if (cardText.length < 12 || !pricePattern.test(cardText)) continue;
            seen.add(href);
            rows.push({ url: href, text: cardText, mallUrl: mallLinkFor(anchor) });
            if (rows.length >= maxItems) break;
          }
          return rows;
        }
        """,
        {"maxItems": max_items},
    ) or []


def extract_search_items_from_page_lenient(page: Page, *, max_items: int = 40) -> list[dict]:
    """更宽松的搜索结果抽取：不强依赖 pricePattern，交给 Python 后处理解析价格。"""
    return page.evaluate(
        """
        ({ maxItems }) => {
          const anchors = Array.from(document.querySelectorAll('a[href]'));
          const seen = new Set();
          const rows = [];
          const productHints = /(goods|product|item|sku|_oak|\\bg-\\d|\\bpd-\\d)/i;
          const textOf = (node) => ((node && (node.innerText || node.textContent)) || '')
            .replace(/[ \\t]+/g, ' ')
            .trim();
          const cardTextFor = (anchor) => {
            let node = anchor;
            let best = textOf(anchor);
            for (let depth = 0; node && depth < 7; depth += 1) {
              const current = textOf(node);
              if (current && current.length > best.length && current.length < 1200) best = current;
              node = node.parentElement;
            }
            return best;
          };
          const mallLinkFor = (anchor) => {
            let node = anchor;
            for (let depth = 0; node && depth < 7; depth += 1) {
              const mallLink = node.querySelector && node.querySelector('a[href*="mall_id"], a[href*="mall.html"]');
              if (mallLink && mallLink.href) return mallLink.href;
              node = node.parentElement;
            }
            return '';
          };
          for (const anchor of anchors) {
            const href = anchor.href || anchor.getAttribute('href') || '';
            if (!href || seen.has(href)) continue;
            const cardText = cardTextFor(anchor);
            if (!productHints.test(href) && cardText.length < 12) continue;
            seen.add(href);
            rows.push({ url: href, text: cardText, mallUrl: mallLinkFor(anchor) });
            if (rows.length >= maxItems) break;
          }
          return rows;
        }
        """,
        {"maxItems": max_items},
    ) or []


def build_discovery_candidates(
    items: list[dict],
    *,
    search_url: str,
    keyword: str,
    limit: int = DEFAULT_DISCOVERY_LIMIT,
) -> list[dict]:
    grouped: OrderedDict[str, dict] = OrderedDict()
    fallback_products: list[dict] = []

    for item in items or []:
        product = normalize_sample_product(item)
        if not product["name"] or product["price"] <= 0:
            continue
        if not is_product_url(product["url"]):
            continue
        mall_id = mall_id_from_item(item)
        if not mall_id:
            fallback_products.append(product)
            continue
        key = f"mall:{mall_id}"
        if key not in grouped:
            grouped[key] = {
                "label": product["name"],
                "url": mall_url(mall_id),
                "sourceType": "shop",
                "sourceKeyword": keyword,
                "sampleProducts": [],
            }
        grouped[key]["sampleProducts"].append(product)

    candidates = list(grouped.values())
    if not candidates and fallback_products:
        candidates.append(
            {
                "label": f"{keyword} 搜索结果候选源",
                "url": search_url,
                "sourceType": "search",
                "sourceKeyword": keyword,
                "sampleProducts": fallback_products[: min(len(fallback_products), 10)],
            }
        )

    result = []
    for rank, candidate in enumerate(candidates[:limit], start=1):
        samples = candidate["sampleProducts"][:5]
        result.append(
            {
                "rank": rank,
                "label": candidate["label"][:80],
                "url": candidate["url"],
                "host": host_of(candidate["url"]),
                "sourceKeyword": candidate["sourceKeyword"],
                "sourceType": candidate["sourceType"],
                "sampleProductCount": len(candidate["sampleProducts"]),
                "sampleProducts": samples,
                "crawlable": bool(samples),
            }
        )
    return result


def normalize_sample_product(item: dict) -> dict:
    text = item.get("text", "")
    url = item.get("url", "")
    return {
        "name": extract_name(text, "Temu fishing product"),
        "url": url,
        "price": extract_price(text),
        "salesSignal": extract_sales_signal(text),
    }


def is_product_url(url: str) -> bool:
    return bool(PRODUCT_URL_RE.search(url or ""))


def mall_id_from_item(item: dict) -> str:
    for url in (item.get("mallUrl", ""), item.get("url", "")):
        parsed = urlparse(url or "")
        query = parse_qs(parsed.query)
        for key in ("mall_id", "mallId", "mallid"):
            values = query.get(key)
            if values and values[0]:
                return values[0][:80]
    return ""


def mall_url(mall_id: str) -> str:
    return f"https://www.temu.com/mall.html?mall_id={mall_id}"


def host_of(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""
