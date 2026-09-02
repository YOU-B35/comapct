"""Douyin (抖店) Agent tasks: login / probe / products sync."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from app.browser.douyin_context import (
    DOUYIN_SELLER_HOME,
    close_douyin_profile_browsers,
    ensure_douyin_home_page,
    install_douyin_only_tab_guard,
    launch_douyin_persistent_context,
    sanitize_profile_startup_for_douyin,
)
from app.timezone import SHANGHAI
from app.config import sync_headless_enabled
from app.observability.task_timing import timed_stage
from app.session_scope import normalize_session_key, resolve_platform_profile_dir

# Frozen from Day0 probe (2026-08-13).
DOUYIN_ORDERS_XHR_READY = True
DOUYIN_PRODUCTS_XHR_READY = True
DOUYIN_COMPASS_XHR_READY = True
DOUYIN_OPPORTUNITY_XHR_READY = True

DOUYIN_GOODS_LIST_URLS = (
    "https://fxg.jinritemai.com/ffa/g/list",
    "https://fxg.jinritemai.com/ffa/goods/list",
)

DOUYIN_ORDER_LIST_PAGE = "https://fxg.jinritemai.com/ffa/morder/order/list"
DOUYIN_ORDER_LIST_API = "https://fxg.jinritemai.com/api/order/searchlist"
DOUYIN_COMPASS_PAGE = "https://compass.jinritemai.com/shop?dateType=1"
DOUYIN_COMPASS_CORE_API = "/compass_api/shop/common/homepage/core_index_v3"
DOUYIN_COMPASS_SUMMARY_API = "/compass_api/shop/common/homepage/summary_core_index_v3"
DOUYIN_COMPASS_EXP_API = "/compass_api/shop/common/homepage/core/prof_exp_score"

# Probed 2026-08-13: 实时=1, 近1天=20, 近7天=21, 近30天=23
DOUYIN_COMPASS_DATE_TYPES: list[dict[str, Any]] = [
    {"date_type": 1, "label": "实时", "window": "realtime"},
    {"date_type": 20, "label": "近1天", "window": "d1"},
    {"date_type": 21, "label": "近7天", "window": "d7"},
    {"date_type": 23, "label": "近30天", "window": "d30"},
]

DOUYIN_OPPORTUNITY_PAGE = "https://fxg.jinritemai.com/ffa/bu/NewBusinessCenter"
DOUYIN_OPPORTUNITY_LIST_API = "/api/commop/business_chance_center/clue/common/real_time_list"
DOUYIN_OPPORTUNITY_DETAIL_API = "/api/commop/business_chance_center/clue/detail"
DOUYIN_OPPORTUNITY_CATEGORY_API = "/api/commop/business_chance_center/shop_full_category/list"

# pool → clue_type_new / default sort / UI label
# 跟潜力爆品 = 9；追抖音热词 = 11（2026-08-13 复测点击冻结）
DOUYIN_OPPORTUNITY_POOLS: dict[str, dict[str, Any]] = {
    "potential": {
        "clue_type_new": 9,
        "label": "跟潜力爆品",
        "default_sort": "MATCH_DEGREE",
    },
    "hot_words": {
        "clue_type_new": 11,
        "label": "追抖音热词",
        "default_sort": "MATCH_DEGREE",
    },
}
DOUYIN_OPPORTUNITY_SORTS: dict[str, str] = {
    "MATCH_DEGREE": "为你推荐",
    "TRADING_AMOUNT": "成交高",
    "PAY_AMOUNT_RATE": "增速快",
    "DEMAND_SUPPLY_RATE": "竞争小",
}

# Frozen from Day0 probe (2026-08-13): browser goods list API.
DOUYIN_PRODUCT_LIST_API = "https://fxg.jinritemai.com/product/tproduct/list"
# Browser uses 0-based page; keep the same query shape as onSale list.
DOUYIN_PRODUCT_LIST_TABS = (
    "onSale",
    "soldOut",
    "draft",
    "offline",
    "all",
)

# ByteDance seller auth cookies — page chrome markers alone are NOT enough.
_AUTH_COOKIE_MARKERS = (
    "sessionid",
    "sessionid_ss",
    "sid_tt",
    "sid_guard",
    "uid_tt",
    "uid_tt_ss",
    "sid_ucp",
    "ssid_ucp",
    "odin_tt",
    "toutiao_sso_user",
)

_LOGIN_CTA_MARKERS = (
    "扫码登录",
    "手机号登录",
    "请登录",
    "验证码登录",
    "登录商家后台",
    "立即登录",
    "账号登录",
)

ROOT = Path(__file__).resolve().parents[1]


def profile_dir(tenant_id: int, store_id: str | None = None) -> Path:
    key = normalize_session_key(store_id)
    if key == "default":
        # 兼容旧版：default 店铺沿用平铺 tenant-{id}，避免既有登录态失效
        legacy = ROOT / ".douyin-browser-profile" / f"tenant-{int(tenant_id)}"
        legacy.mkdir(parents=True, exist_ok=True)
        return legacy
    path = resolve_platform_profile_dir(
        "douyin",
        tenant_id,
        key,
        root=ROOT / ".douyin-browser-profile",
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_in_clean_thread(fn, *, timeout: float | None = None):
    """Playwright Sync API cannot run when the current thread already has an asyncio loop
    (Helper tray/flask may install one). Always execute browser work on a fresh thread.
    """
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        return fut.result(timeout=timeout)


def _douyin_launch_kwargs(*, headless: bool) -> dict[str, Any]:
    """统一使用 Playwright 内置 Chromium（不打开系统 Chrome/Edge，避免风控）。"""
    from app.browser.context import _bundled_chromium_ready

    kwargs: dict[str, Any] = {
        "headless": headless,
        "viewport": {"width": 1440, "height": 900},
        "locale": "zh-CN",
        # Persistent profile already has extension state; Playwright's
        # --disable-extensions makes Chrome exit immediately (target closed).
        "ignore_default_args": ["--enable-automation", "--disable-extensions"],
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
            "--hide-crash-restore-bubble",
            f"--homepage={DOUYIN_SELLER_HOME}",
        ],
    }
    if not _bundled_chromium_ready():
        raise RuntimeError(
            "DOUYIN_BROWSER_UNAVAILABLE: 未检测到 Playwright 内置 Chromium。"
            "抖音登录/同步统一使用内置浏览器（不打开系统 Chrome/Edge），"
            "请先执行 python -m playwright install chromium 后重试"
        )
    return kwargs


def _has_douyin_profile_lock(profile_dir: Path) -> bool:
    root = Path(profile_dir)
    if (root / "SingletonLock").exists() or (root / "lockfile").exists():
        return True
    return (root / "Default" / "LOCK").exists()


def _launch(
    tenant_id: int,
    *,
    headless: bool = False,
    force_navigate: bool = True,
    store_id: str | None = None,
):
    from playwright.sync_api import sync_playwright

    user_dir = profile_dir(tenant_id, store_id)
    # Kill holders first. Mutating Preferences/Sessions under a live Chrome
    # makes the next launch exit immediately ("Target page ... has been closed").
    if _has_douyin_profile_lock(user_dir):
        print("[DouyinBrowser] stale profile lock present, reclaiming before launch…", flush=True)
        close_douyin_profile_browsers(user_dir)
    sanitize_profile_startup_for_douyin(user_dir, home_url=DOUYIN_SELLER_HOME)
    launch_kwargs = _douyin_launch_kwargs(headless=headless)
    state: dict[str, Any] = {"pw": None}

    def launch_fn():
        if state["pw"] is not None:
            _close_pw(state["pw"], None)
            state["pw"] = None
        state["pw"] = sync_playwright().start()
        return state["pw"].chromium.launch_persistent_context(
            user_data_dir=str(user_dir),
            **launch_kwargs,
        )

    try:
        context = launch_douyin_persistent_context(
            playwright=None,
            profile_dir=user_dir,
            launch_kwargs=launch_kwargs,
            launch_fn=launch_fn,
            reclaim_fn=lambda: close_douyin_profile_browsers(user_dir),
        )
    except Exception:
        _close_pw(state["pw"], None)
        raise
    install_douyin_only_tab_guard(context)
    page = ensure_douyin_home_page(context, force_navigate=force_navigate)
    return state["pw"], context, page


def _cookie_summary(context) -> str:
    try:
        cookies = context.cookies()
    except Exception:
        return "cookies=unreadable"
    names = sorted({str(c.get("name") or "") for c in cookies if c.get("name")})
    auth_hits = [n for n in names if any(m in n.lower() for m in _AUTH_COOKIE_MARKERS)]
    return f"cookies={len(names)} auth={auth_hits[:8] or '-'}"


def _has_auth_cookies(context) -> bool:
    try:
        cookies = context.cookies()
    except Exception:
        return False
    for cookie in cookies:
        name = str(cookie.get("name") or "").lower()
        domain = str(cookie.get("domain") or "").lower()
        if not any(host in domain for host in ("jinritemai", "douyin", "bytedance", "ecombd")):
            continue
        if any(marker in name for marker in _AUTH_COOKIE_MARKERS):
            return True
    return False


def _looks_logged_in(page, context=None) -> bool:
    """Require real auth cookies + console chrome; reject login CTA pages."""
    url = (page.url or "").lower()
    if "login" in url or "passport" in url or "sso" in url:
        return False
    if "fxg.jinritemai.com" not in url:
        return False
    try:
        body = page.inner_text("body", timeout=3000)
    except Exception:
        body = ""
    if any(marker in body for marker in _LOGIN_CTA_MARKERS):
        return False
    markers = ("订单", "商品", "售后", "数据", "首页", "抖店")
    hits = sum(1 for m in markers if m in body)
    if hits < 2:
        return False
    # Critical: shell text without seller auth cookies used to false-positive「已登录」.
    if context is not None and not _has_auth_cookies(context):
        return False
    return True


def _wait_until_logged_in(page, context, *, timeout_seconds: int, label: str):
    deadline = time.time() + max(30, int(timeout_seconds))
    last_log = 0.0
    current = page
    while time.time() < deadline:
        try:
            from app.browser.douyin_context import close_foreign_douyin_pages

            close_foreign_douyin_pages(context)
        except Exception:
            pass
        try:
            if "fxg.jinritemai.com" not in (current.url or "").lower():
                current = ensure_douyin_home_page(context, force_navigate=False)
        except Exception:
            pass
        if _looks_logged_in(current, context):
            # Give Chromium a moment to flush remaining auth cookies.
            time.sleep(1.5)
            if _looks_logged_in(current, context):
                print(f"[DouyinLogin] {label} ready {_cookie_summary(context)}", flush=True)
                return True, current
        now = time.time()
        if now - last_log > 8:
            print(
                f"[DouyinLogin] {label} waiting… url={getattr(current, 'url', '')!r} {_cookie_summary(context)}",
                flush=True,
            )
            last_log = now
        time.sleep(2.0)
    return False, current


def _close_pw(pw, context) -> None:
    try:
        if context is not None:
            context.close()
    except Exception as exc:  # noqa: BLE001
        print(f"[Douyin] context.close: {exc}", flush=True)
    try:
        if pw is not None:
            pw.stop()
    except Exception:
        pass


def _call_with_retry(fn, *, retries: int = 1, delay: float = 1.5, label: str = "") -> Any:
    """Run ``fn``, retrying transient failures (e.g. session not warm yet)."""
    last_error: BaseException | None = None
    for attempt in range(max(1, int(retries) + 1)):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < int(retries):
                print(
                    f"[Douyin] {label} attempt {attempt + 1} failed, retry in {delay}s: {exc}",
                    flush=True,
                )
                time.sleep(max(0.0, float(delay)))
    assert last_error is not None
    raise last_error


def probe_session(tenant_id: int, store_id: str | None = None) -> dict[str, Any]:
    def _run() -> dict[str, Any]:
        pw = context = page = None
        try:
            pw, context, page = _launch(
                tenant_id,
                headless=False,
                force_navigate=True,
                store_id=store_id,
            )
            time.sleep(1.5)
            logged_in = _looks_logged_in(page, context)
            print(
                f"[DouyinProbe] tenant={tenant_id} logged_in={logged_in} "
                f"url={page.url!r} {_cookie_summary(context)}",
                flush=True,
            )
            return {
                "tenant_id": tenant_id,
                "ready": logged_in,
                "logged_in": logged_in,
                "requires_auth": not logged_in,
                "profile_busy": False,
                "message": "抖店已登录" if logged_in else "抖店未登录，请打开登录窗口完成登录",
                "shop_count": 0,
                "shops": [],
            }
        finally:
            _close_pw(pw, context)

    return _run_in_clean_thread(_run, timeout=180)


def open_login_window(
    tenant_id: int,
    timeout_seconds: int = 600,
    store_id: str | None = None,
) -> dict[str, Any]:
    def _run() -> dict[str, Any]:
        pw = context = page = None
        try:
            pw, context, page = _launch(
                tenant_id,
                headless=False,
                force_navigate=True,
                store_id=store_id,
            )
            print(f"[DouyinLogin] opened {DOUYIN_SELLER_HOME} tenant={tenant_id}", flush=True)
            logged_in, page = _wait_until_logged_in(
                page,
                context,
                timeout_seconds=timeout_seconds,
                label="open_login",
            )
            return {
                "tenant_id": tenant_id,
                "ready": logged_in,
                "logged_in": logged_in,
                "requires_auth": not logged_in,
                "profile_busy": False,
                "message": "抖店已登录" if logged_in else "登录超时，请重试打开登录窗口",
                "shop_count": 0,
                "shops": [],
            }
        finally:
            # Graceful close on this thread so cookies flush before next sync.
            _close_pw(pw, context)

    return _run_in_clean_thread(_run, timeout=float(timeout_seconds) + 90)


def _extract_list_rows(data: Any) -> list[dict[str, Any]] | None:
    if not isinstance(data, dict):
        return None
    candidates: list[Any] = []
    node = data.get("data")
    # Douyin /product/tproduct/list returns data as a bare array.
    if isinstance(node, list):
        candidates.append(node)
    elif isinstance(node, dict):
        for key in (
            "product_list",
            "productList",
            "products",
            "list",
            "items",
            "records",
            "data_list",
            "dataList",
        ):
            if isinstance(node.get(key), list):
                candidates.append(node.get(key))
        nested = node.get("data")
        if isinstance(nested, list):
            candidates.append(nested)
        elif isinstance(nested, dict):
            for key in ("product_list", "productList", "list", "items"):
                if isinstance(nested.get(key), list):
                    candidates.append(nested.get(key))
    for key in ("product_list", "productList", "list", "items"):
        if isinstance(data.get(key), list):
            candidates.append(data.get(key))

    for rows in candidates:
        if not rows:
            continue
        sample = rows[0] if isinstance(rows[0], dict) else None
        if not isinstance(sample, dict):
            continue
        if not _row_looks_like_product(sample):
            continue
        return [r for r in rows if isinstance(r, dict) and _row_looks_like_product(r)]
    return None


def _row_looks_like_product(raw: dict[str, Any]) -> bool:
    """Reject 商品分组 / 运费模板 等误匹配；接受 product_id + name/img 等。"""
    keys = {str(k).lower() for k in raw.keys()}
    if "group_id" in keys and not ({"product_id", "productid"} & keys):
        return False
    if "template_name" in keys or "calculate_type" in keys:
        return False
    if "first_num_price" in keys and "product_province" in keys:
        return False

    product_id = raw.get("product_id")
    if product_id in (None, ""):
        product_id = raw.get("productId")
    if product_id in (None, ""):
        nested = raw.get("product") if isinstance(raw.get("product"), dict) else {}
        product_id = nested.get("product_id") or nested.get("productId") or nested.get("id")
    if product_id in (None, ""):
        return False
    blob = json.dumps(raw, ensure_ascii=False).lower()
    return any(
        token in blob
        for token in (
            "product_name",
            "productname",
            '"name"',
            "title",
            "img",
            "stock",
            "price",
            "sell_num",
            "sellnum",
            "sku",
            "check_status",
            "market_price",
            "product_url",
            "shop_id",
        )
    )


def _extract_total_count(data: Any, page_rows: int) -> int:
    if not isinstance(data, dict):
        return page_rows
    candidates: list[Any] = []
    for key in ("total", "total_num", "totalNum", "total_count", "totalCount", "count"):
        if key in data:
            candidates.append(data.get(key))
    node = data.get("data")
    if isinstance(node, dict):
        for key in ("total", "total_num", "totalNum", "total_count", "totalCount", "count"):
            if key in node:
                candidates.append(node.get(key))
        nested = node.get("page_result") or node.get("pageResult") or node.get("pagination")
        if isinstance(nested, dict):
            for key in ("total", "total_num", "totalNum", "total_count", "totalCount"):
                if key in nested:
                    candidates.append(nested.get(key))
    for raw in candidates:
        try:
            value = int(raw)
        except Exception:
            continue
        if value >= page_rows:
            return value
    return page_rows


def _format_douyin_price(raw: Any) -> float | None:
    """Douyin list API prices are usually in 分."""
    if raw in (None, ""):
        return None
    try:
        value = float(raw)
    except Exception:
        return None
    # Heuristic: integer-like fen amounts are commonly >= 1; keep 0 as 0.
    if abs(value - round(value)) < 1e-9 and abs(value) >= 1:
        return round(value / 100.0, 2)
    return value


def _format_unix_or_text(raw: Any) -> str:
    if raw in (None, ""):
        return ""
    if isinstance(raw, (int, float)) and raw > 10_000_000:
        try:
            return datetime.fromtimestamp(int(raw), tz=SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(raw)
    text = str(raw).strip()
    if text.isdigit() and len(text) >= 10:
        try:
            return datetime.fromtimestamp(int(text), tz=SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return text
    return text


def _extract_article_no(raw: dict[str, Any]) -> str:
    for key in (
        "out_product_id",
        "outProductId",
        "outer_product_id",
        "goods_no",
        "goodsNo",
        "article_no",
        "articleNo",
        "art_no",
        "artNo",
    ):
        value = raw.get(key)
        if value not in (None, ""):
            return str(value).strip()
    fmt = raw.get("product_format_new")
    if isinstance(fmt, dict):
        for props in fmt.values():
            if not isinstance(props, list):
                continue
            for prop in props:
                if not isinstance(prop, dict):
                    continue
                prop_name = str(prop.get("PropertyName") or prop.get("property_name") or "")
                if "货号" in prop_name:
                    name = prop.get("name")
                    if name not in (None, ""):
                        return str(name).strip()
    return ""


def _map_product_row(raw: dict[str, Any]) -> dict[str, Any]:
    def pick(*keys: str) -> Any:
        for key in keys:
            if key in raw and raw[key] not in (None, ""):
                return raw[key]
        product = raw.get("product") if isinstance(raw.get("product"), dict) else {}
        for key in keys:
            if key in product and product[key] not in (None, ""):
                return product[key]
        return ""

    product_id = str(pick("product_id", "productId", "product_id_str") or "").strip()
    name = str(pick("product_name", "productName", "name", "title", "goods_name") or "").strip()
    status_raw = pick("tab", "status_desc", "statusDesc", "status_name", "statusName")
    status = str(status_raw if status_raw not in (None, "") else "").strip()
    if not status:
        # Fallback numeric status → readable label is already in tab for list API.
        status = str(pick("status", "check_status", "checkStatus") or "").strip()
    status_label = status
    price = _format_douyin_price(
        pick(
            "discount_price",
            "discountPrice",
            "price_lower",
            "price",
            "sale_price",
            "salePrice",
            "market_price",
            "marketPrice",
        )
    )
    stock = pick("stock_num", "stockNum", "stock", "sku_stock", "skuStock", "self_sell_stock_num")
    sales = pick("sell_num", "sellNum", "sales", "sold_num", "soldNum", "sell_num_30d")
    image = pick("img", "image", "main_img", "mainImg", "img_url", "imgUrl", "cover")
    if isinstance(image, list) and image:
        image = image[0]
    category = pick("category_name", "categoryName", "category", "cate_name")
    article_no = _extract_article_no(raw)
    quality_score = pick("quality_score", "qualityScore", "base_score", "baseScore")
    published_at = _format_unix_or_text(
        pick("create_time", "createTime", "publish_time", "publishTime", "audit_time", "auditTime")
    )
    good_rate_raw = pick("comment_percent", "commentPercent", "good_rate", "goodRate", "comment_good")
    good_rate = None
    if good_rate_raw not in (None, ""):
        try:
            rate = float(good_rate_raw)
            # API may return 0-1 or 0-100.
            if 0 <= rate <= 1:
                rate = rate * 100.0
            good_rate = round(rate, 2)
        except Exception:
            good_rate = None
    skus = pick("skus", "sku_list", "skuList", "spec_list")
    return {
        "product_id": product_id,
        "product_name": name,
        "status": status,
        "status_label": status_label,
        "price": price,
        "stock": stock if stock != "" else None,
        "sales": sales if sales != "" else None,
        "main_image": str(image or ""),
        "category": str(category or ""),
        "article_no": article_no,
        "quality_score": quality_score if quality_score != "" else None,
        "published_at": published_at,
        "good_rate": good_rate,
        "sku_count": len(skus) if isinstance(skus, list) else 0,
        "skus_json": json.dumps(skus, ensure_ascii=False) if isinstance(skus, (list, dict)) else "",
        "raw_json": json.dumps(raw, ensure_ascii=False),
    }


def _dedupe_products(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("product_id") or "") or str(row.get("product_name") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _build_product_list_url(page_no: int, page_size: int, *, tab: str = "onSale") -> str:
    from urllib.parse import urlencode

    params = {
        "page": str(page_no),
        "pageSize": str(page_size),
        "draft_status": "0",
        "comment_percent": "",
        "group_id": "",
        "sku_type": "",
        "tab": tab,
        "business_type": "4",
        "is_online": "1" if tab == "onSale" else "",
        "not_for_sale_search_type": "1",
        "from_mng": "1",
        "check_status": "3" if tab == "onSale" else "",
        "status": "0" if tab == "onSale" else "",
        "supply_status": "",
        "need_auto_rectify_info": "true",
        "need_pay_no_stock_skus": "true",
        "order_field": "audit_time",
        "sort": "desc",
        "appid": "1",
    }
    # Drop empty values for cleaner requests on non-onSale tabs.
    clean = {k: v for k, v in params.items() if v != ""}
    return f"{DOUYIN_PRODUCT_LIST_API}?{urlencode(clean)}"


def _fetch_product_list_page(page, *, page_no: int, page_size: int, tab: str = "onSale") -> tuple[list[dict[str, Any]], int, str]:
    url = _build_product_list_url(page_no, page_size, tab=tab)
    print(f"[DouyinProducts] GET tab={tab} page={page_no} size={page_size}", flush=True)
    with timed_stage("douyin_products.request"):
        response = page.request.get(url, timeout=60_000)
    if response.status >= 400:
        raise RuntimeError(f"product list HTTP {response.status} tab={tab} page={page_no}")
    try:
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"product list invalid json tab={tab} page={page_no}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"product list unexpected body tab={tab} page={page_no}")
    # code/st can be 0 on success
    rows = _extract_list_rows(data) or []
    mapped: list[dict[str, Any]] = []
    for row in rows:
        item = _map_product_row(row)
        if item.get("product_id"):
            mapped.append(item)
    total = _extract_total_count(data, len(mapped))
    return mapped, total, url


def fetch_products_via_xhr(page) -> tuple[list[dict[str, Any]], str]:
    """Open 商品管理 to warm session, then page /product/tproduct/list until total."""
    last_error = ""
    warmed = False
    for list_url in DOUYIN_GOODS_LIST_URLS:
        try:
            print(f"[DouyinProducts] goto {list_url}", flush=True)
            page.goto(list_url, wait_until="domcontentloaded", timeout=90_000)
            time.sleep(0.4)
            warmed = True
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            print(f"[DouyinProducts] goto failed {list_url}: {exc}", flush=True)
    if not warmed:
        raise RuntimeError(
            "DY_PRODUCTS_SOURCE_UNAVAILABLE: 无法打开商品管理页。"
            + (f" last_error={last_error}" if last_error else "")
        )

    page_size = 100
    all_rows: list[dict[str, Any]] = []
    source_url = DOUYIN_PRODUCT_LIST_API
    seen_tabs_total = 0

    for tab in DOUYIN_PRODUCT_LIST_TABS:
        tab_rows: list[dict[str, Any]] = []
        try:
            first, total_hint, source_url = _call_with_retry(
                lambda tab=tab: _fetch_product_list_page(
                    page, page_no=0, page_size=page_size, tab=tab
                ),
                label=f"products page0 tab={tab}",
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[DouyinProducts] tab={tab} page0 failed: {exc}", flush=True)
            continue
        if not first and total_hint <= 0:
            print(f"[DouyinProducts] tab={tab} empty, skip", flush=True)
            continue
        tab_rows.extend(first)
        print(
            f"[DouyinProducts] tab={tab} got={len(first)} total_hint={total_hint}",
            flush=True,
        )
        # Douyin list page is 0-based.
        page_no = 1
        max_pages = max(1, min(200, (max(total_hint, 1) + page_size - 1) // page_size + 2))
        while page_no < max_pages and len(_dedupe_products(tab_rows)) < max(total_hint, 1):
            try:
                batch, total_hint, source_url = _fetch_product_list_page(
                    page, page_no=page_no, page_size=page_size, tab=tab
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[DouyinProducts] tab={tab} page={page_no} failed: {exc}", flush=True)
                break
            if not batch:
                break
            tab_rows.extend(batch)
            print(
                f"[DouyinProducts] tab={tab} accumulated={len(_dedupe_products(tab_rows))} total_hint={total_hint}",
                flush=True,
            )
            if len(batch) < page_size:
                break
            page_no += 1
            time.sleep(0.2)

        before = len(_dedupe_products(all_rows))
        all_rows.extend(tab_rows)
        after = len(_dedupe_products(all_rows))
        seen_tabs_total += max(total_hint, len(tab_rows))
        print(
            f"[DouyinProducts] tab={tab} unique_added={after - before} running_unique={after}",
            flush=True,
        )
        # If onSale already covers the shop total, skip remaining tabs.
        if tab == "onSale" and total_hint >= 400 and after >= total_hint:
            break

    unique = _dedupe_products(all_rows)
    if not unique:
        raise RuntimeError(
            "DY_PRODUCTS_SOURCE_UNAVAILABLE: 未获取到商品列表。"
            " 请确认已登录抖店并打开商品管理后重试"
        )
    print(
        f"[DouyinProducts] done count={len(unique)} tabs_total_hint≈{seen_tabs_total} source={source_url}",
        flush=True,
    )
    return unique, source_url


def _resolve_store_id(client, tenant_id: int, store_id: str) -> str:
    store_id = (store_id or "").strip()
    if store_id:
        return store_id
    try:
        accounts = client.list_platform_accounts(tenant_id) or {}
    except Exception:
        accounts = {}
    douyin = accounts.get("douyin") or accounts.get("items") or []
    if isinstance(douyin, list) and len(douyin) == 1:
        return str(douyin[0].get("id") or "").strip()
    if isinstance(douyin, list) and douyin:
        # Prefer first bound shop when mapping not required
        return str(douyin[0].get("id") or "").strip()
    return ""


def run_products_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    job_id = str(payload.get("job_id") or "")
    store_id = _resolve_store_id(client, tenant_id, str(payload.get("store_id") or ""))

    if not DOUYIN_PRODUCTS_XHR_READY:
        raise RuntimeError("DY_PRODUCTS_SOURCE_UNAVAILABLE: 商品接口尚未就绪")

    pw = context = page = None
    try:
        pw, context, page = _launch(
            tenant_id,
            headless=sync_headless_enabled(),
            force_navigate=True,
            store_id=store_id,
        )
        if not _looks_logged_in(page, context):
            if sync_headless_enabled():
                raise RuntimeError(
                    "DY_NOT_LOGGED_IN: 抖音未登录（无头模式不弹窗）。请先点「打开登录」完成登录后再同步"
                )
            print(
                f"[DouyinProducts] not logged in yet; keep window open for login "
                f"{_cookie_summary(context)}",
                flush=True,
            )
            logged_in, page = _wait_until_logged_in(
                page,
                context,
                timeout_seconds=300,
                label="products_sync",
            )
            if not logged_in:
                raise RuntimeError("DY_NOT_LOGGED_IN: 抖音商家后台未登录，请打开登录窗口完成登录")
        products, source_url = fetch_products_via_xhr(page)
    finally:
        _close_pw(pw, context)


    if not store_id:
        store_id = "default"

    ingest_body = {
        "job_id": job_id,
        "store_id": store_id,
        "source_url": source_url,
        "products": products,
    }
    client.ingest_douyin_products(ingest_body)
    now = datetime.now(SHANGHAI).isoformat()
    return {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "scope": "products",
        "products_count": len(products),
        "orders_count": 0,
        "issues_count": 0,
        "partial": False,
        "message": f"已同步商品 {len(products)} 条",
        "synced_at": now,
        "source_url": source_url,
    }


def _orders_window_24h() -> tuple[datetime, datetime, list[str]]:
    """Rolling window: yesterday same clock time → now (Asia/Shanghai)."""
    end = datetime.now(SHANGHAI).replace(microsecond=0)
    start = end - timedelta(days=1)
    days: list[str] = []
    day = start.date()
    while day <= end.date():
        days.append(day.isoformat())
        day = day + timedelta(days=1)
    return start, end, days


def _sku_label(item: dict[str, Any]) -> str:
    code = str(item.get("merchant_sku_code") or "").strip()
    if code:
        return code
    sku_id = str(item.get("sku_id_str") or item.get("sku_id") or "").strip()
    specs = item.get("sku_spec")
    if isinstance(specs, list) and specs:
        parts: list[str] = []
        for spec in specs:
            if not isinstance(spec, dict):
                continue
            name = str(spec.get("name") or "").strip()
            value = str(spec.get("value") or "").strip()
            if name and value:
                parts.append(f"{name}:{value}")
            elif value:
                parts.append(value)
        if parts:
            return " / ".join(parts)
    return sku_id


def _order_status_text(raw: dict[str, Any], item: dict[str, Any] | None = None) -> str:
    info = raw.get("order_status_info")
    if isinstance(info, dict):
        text = str(info.get("order_status_text") or "").strip()
        if text:
            return text
    if item:
        for key in ("item_order_status_desc", "package_status_desc"):
            text = str(item.get(key) or "").strip()
            if text:
                return text
    status = raw.get("order_status")
    return str(status) if status not in (None, "") else "待处理"


def _map_order_lines(raw: dict[str, Any]) -> list[dict[str, Any]]:
    order_no = str(
        raw.get("shop_order_id")
        or raw.get("order_id")
        or raw.get("order_id_for_show")
        or ""
    ).strip()
    ordered_at = str(raw.get("create_time_str") or "").strip() or _format_unix_or_text(
        raw.get("create_time")
    )
    report_day = ""
    if ordered_at:
        report_day = ordered_at[:10]
    elif raw.get("create_time") not in (None, ""):
        try:
            report_day = datetime.fromtimestamp(int(raw["create_time"]), tz=SHANGHAI).strftime(
                "%Y-%m-%d"
            )
        except Exception:
            report_day = ""
    ship_deadline = _format_unix_or_text(raw.get("exp_ship_time"))
    channel = str(
        raw.get("c_biz_desc") or raw.get("b_type_desc") or raw.get("store_name") or ""
    ).strip()
    status = _order_status_text(raw)
    raw_json = json.dumps(raw, ensure_ascii=False)
    items = raw.get("product_item")
    if not isinstance(items, list) or not items:
        amount = _format_douyin_price(raw.get("actual_pay_amount") or raw.get("pay_amount"))
        return [
            {
                "order_no": order_no,
                "product_name": "",
                "sku": "",
                "quantity": int(raw.get("product_count") or raw.get("total_product_count") or 1),
                "amount": amount if amount is not None else 0.0,
                "currency": "CNY",
                "status": status,
                "channel": channel,
                "ordered_at": ordered_at,
                "ship_deadline": ship_deadline,
                "report_day": report_day,
                "raw_json": raw_json,
            }
        ]
    lines: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        amount = _format_douyin_price(
            item.get("pay_amount")
            if item.get("pay_amount") not in (None, "")
            else raw.get("actual_pay_amount")
        )
        qty = item.get("combo_num")
        try:
            quantity = int(qty) if qty not in (None, "") else 1
        except Exception:
            quantity = 1
        lines.append(
            {
                "order_no": order_no,
                "product_name": str(item.get("product_name") or "").strip(),
                "sku": _sku_label(item),
                "quantity": quantity,
                "amount": amount if amount is not None else 0.0,
                "currency": "CNY",
                "status": _order_status_text(raw, item),
                "channel": channel,
                "ordered_at": ordered_at,
                "ship_deadline": ship_deadline,
                "report_day": report_day,
                "raw_json": raw_json,
            }
        )
    return lines or [
        {
            "order_no": order_no,
            "product_name": "",
            "sku": "",
            "quantity": 1,
            "amount": 0.0,
            "currency": "CNY",
            "status": status,
            "channel": channel,
            "ordered_at": ordered_at,
            "ship_deadline": ship_deadline,
            "report_day": report_day,
            "raw_json": raw_json,
        }
    ]


def _fetch_order_list_page(
    page,
    *,
    page_no: int,
    page_size: int,
    start_ts: int,
    end_ts: int,
) -> tuple[list[dict[str, Any]], int]:
    params = {
        "page": str(page_no),
        "pageSize": str(page_size),
        "order_by": "create_time",
        "order": "desc",
        "tab": "all",
        "create_time_start": str(start_ts),
        "create_time_end": str(end_ts),
        "appid": "1",
    }
    url = f"{DOUYIN_ORDER_LIST_API}?{urlencode(params)}"
    with timed_stage("douyin_orders.request"):
        resp = page.request.get(url, timeout=60_000)
    if resp.status >= 400:
        raise RuntimeError(f"searchlist HTTP {resp.status}")
    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError("searchlist 响应非 JSON 对象")
    code = data.get("code", data.get("st"))
    if code not in (0, "0", None, ""):
        raise RuntimeError(f"searchlist code={code} msg={data.get('msg') or data.get('message')}")
    rows = data.get("data")
    if not isinstance(rows, list):
        rows = []
    total = 0
    try:
        total = int(data.get("total") or 0)
    except Exception:
        total = len(rows)
    return rows, total


def fetch_orders_via_xhr(page) -> tuple[list[dict[str, Any]], str]:
    start, end, _days = _orders_window_24h()
    start_ts = int(start.timestamp())
    end_ts = int(end.timestamp())
    print(
        f"[DouyinOrders] window {start.isoformat()} .. {end.isoformat()} "
        f"ts={start_ts}..{end_ts}",
        flush=True,
    )
    try:
        page.goto(DOUYIN_ORDER_LIST_PAGE, wait_until="domcontentloaded", timeout=90_000)
        time.sleep(0.4)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"DY_ORDERS_SOURCE_UNAVAILABLE: 无法打开订单管理页: {exc}") from exc

    page_size = 100
    all_raw: list[dict[str, Any]] = []
    try:
        first, total_hint = _call_with_retry(
            lambda: _fetch_order_list_page(
                page, page_no=0, page_size=page_size, start_ts=start_ts, end_ts=end_ts
            ),
            label="orders page0",
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"DY_ORDERS_SOURCE_UNAVAILABLE: 订单列表接口失败: {exc}") from exc

    all_raw.extend(first)
    print(f"[DouyinOrders] page0 got={len(first)} total_hint={total_hint}", flush=True)
    page_no = 1
    max_pages = max(1, min(400, (max(total_hint, 1) + page_size - 1) // page_size + 2))
    while page_no < max_pages and len(all_raw) < max(total_hint, 1):
        try:
            batch, total_hint = _fetch_order_list_page(
                page, page_no=page_no, page_size=page_size, start_ts=start_ts, end_ts=end_ts
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[DouyinOrders] page={page_no} failed: {exc}", flush=True)
            break
        if not batch:
            break
        all_raw.extend(batch)
        print(
            f"[DouyinOrders] page={page_no} accumulated={len(all_raw)} total_hint={total_hint}",
            flush=True,
        )
        if len(batch) < page_size:
            break
        page_no += 1
        time.sleep(0.2)

    if not all_raw and total_hint <= 0:
        print("[DouyinOrders] empty window — still ingest empty days", flush=True)

    mapped: list[dict[str, Any]] = []
    for raw in all_raw:
        if not isinstance(raw, dict):
            continue
        # Safety: local filter if API ever ignores time params.
        try:
            ct = int(raw.get("create_time") or 0)
        except Exception:
            ct = 0
        if ct and (ct < start_ts or ct > end_ts):
            continue
        mapped.extend(_map_order_lines(raw))

    print(f"[DouyinOrders] mapped_lines={len(mapped)} orders={len(all_raw)}", flush=True)
    return mapped, DOUYIN_ORDER_LIST_API


def run_orders_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    job_id = str(payload.get("job_id") or "")
    store_id = str(payload.get("store_id") or "").strip()

    if not DOUYIN_ORDERS_XHR_READY:
        raise RuntimeError(
            "DY_ORDERS_SOURCE_UNAVAILABLE: 订单接口尚未完成 Day0 探测固化"
        )

    store_id = _resolve_store_id(client, tenant_id, store_id)
    if not store_id:
        store_id = "default"

    pw = context = page = None
    try:
        pw, context, page = _launch(
            tenant_id,
            headless=sync_headless_enabled(),
            force_navigate=True,
            store_id=store_id,
        )
        if not _looks_logged_in(page, context):
            if sync_headless_enabled():
                raise RuntimeError(
                    "DY_NOT_LOGGED_IN: 抖音未登录（无头模式不弹窗）。请先点「打开登录」完成登录后再同步"
                )
            print(
                f"[DouyinOrders] not logged in yet; keep window open for login "
                f"{_cookie_summary(context)}",
                flush=True,
            )
            logged_in, page = _wait_until_logged_in(
                page,
                context,
                timeout_seconds=300,
                label="orders_sync",
            )
            if not logged_in:
                raise RuntimeError("DY_NOT_LOGGED_IN: 抖音商家后台未登录，请打开登录窗口完成登录")
        orders, source_url = fetch_orders_via_xhr(page)
    finally:
        _close_pw(pw, context)

    _start, _end, day_list = _orders_window_24h()
    by_day: dict[str, list[dict[str, Any]]] = {d: [] for d in day_list}
    for row in orders:
        day = str(row.get("report_day") or "").strip()
        if day not in by_day:
            # Outside window after local filter miss — skip
            continue
        by_day[day].append(row)

    days_payload = [
        {"replace_day": day, "orders": by_day.get(day, [])}
        for day in day_list
    ]
    ingest_body = {
        "job_id": job_id,
        "store_id": store_id,
        "source_url": source_url,
        "days": days_payload,
        "window_start": _start.strftime("%Y-%m-%d %H:%M:%S"),
        "window_end": _end.strftime("%Y-%m-%d %H:%M:%S"),
    }
    client.ingest_douyin_orders(ingest_body)
    total = sum(len(d["orders"]) for d in days_payload)
    return {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "scope": "orders",
        "orders_count": total,
        "issues_count": 0,
        "partial": False,
        "message": f"已同步近24小时订单 {total} 条",
        "synced_at": datetime.now(SHANGHAI).isoformat(),
        "source_url": source_url,
    }


def run_issues_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    """Sync content warnings (violation + product diagnose; live/short_video UNCONFIGURED)."""
    from agent.douyin_issues import collect_issues

    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    job_id = str(payload.get("job_id") or "")
    store_id = _resolve_store_id(client, tenant_id, str(payload.get("store_id") or ""))
    if not store_id:
        store_id = "default"

    pw = context = page = None
    try:
        pw, context, page = _launch(
            tenant_id,
            headless=sync_headless_enabled(),
            force_navigate=True,
            store_id=store_id,
        )
        if not _looks_logged_in(page, context):
            if sync_headless_enabled():
                raise RuntimeError(
                    "DY_NOT_LOGGED_IN: 抖音未登录（无头模式不弹窗）。请先点「打开登录」完成登录后再同步"
                )
            print(
                f"[DouyinIssues] not logged in yet; keep window open for login "
                f"{_cookie_summary(context)}",
                flush=True,
            )
            logged_in, page = _wait_until_logged_in(
                page,
                context,
                timeout_seconds=300,
                label="issues_sync",
            )
            if not logged_in:
                raise RuntimeError("DY_NOT_LOGGED_IN: 抖音商家后台未登录，请打开登录窗口完成登录")
        issues, meta = collect_issues(page, context)
    finally:
        _close_pw(pw, context)

    partial = bool(meta.get("partial"))
    reasons = meta.get("partial_reasons") or []
    reason_text = ",".join(str(r) for r in reasons[:6])
    sources_ok = meta.get("sources_ok") or []
    message = f"已同步内容预警 {len(issues)} 条"
    if sources_ok:
        message += f"（源: {','.join(sources_ok)}）"
    if partial:
        message += f"；部分源跳过/失败"
        if reason_text:
            message += f"：{reason_text[:180]}"

    ingest_body = {
        "job_id": job_id,
        "store_id": store_id,
        "issues": issues,
        "partial": partial,
        "partial_reason": reason_text,
        "message": message,
    }
    client.ingest_douyin_issues(ingest_body)
    return {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "scope": "issues",
        "orders_count": 0,
        "issues_count": len(issues),
        "partial": partial,
        "partial_reason": reason_text,
        "message": message,
        "synced_at": datetime.now(SHANGHAI).isoformat(),
        "sources_ok": sources_ok,
    }


def run_all_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    """一次浏览器会话内同步 商品 + 订单 + 内容预警（避免每个 scope 重复启动浏览器）。"""
    from agent.douyin_issues import collect_issues

    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    job_id = str(payload.get("job_id") or "")
    store_id = _resolve_store_id(client, tenant_id, str(payload.get("store_id") or ""))
    if not store_id:
        store_id = "default"

    headless = sync_headless_enabled()
    pw = context = page = None
    try:
        pw, context, page = _launch(
            tenant_id,
            headless=headless,
            force_navigate=True,
            store_id=store_id,
        )
        if not _looks_logged_in(page, context):
            if headless:
                raise RuntimeError(
                    "DY_NOT_LOGGED_IN: 抖音未登录（无头模式不弹窗）。请先点「打开登录」完成登录后再同步"
                )
            logged_in, page = _wait_until_logged_in(
                page,
                context,
                timeout_seconds=300,
                label="all_sync",
            )
            if not logged_in:
                raise RuntimeError("DY_NOT_LOGGED_IN: 抖音商家后台未登录，请打开登录窗口完成登录")

        products, product_source = fetch_products_via_xhr(page)
        orders, order_source = fetch_orders_via_xhr(page)

        issues: list[dict[str, Any]] = []
        partial = False
        partial_reason = ""
        try:
            issues, meta = collect_issues(page, context)
            partial = bool(meta.get("partial"))
            partial_reason = ",".join(str(r) for r in (meta.get("partial_reasons") or [])[:6])
        except Exception as exc:  # noqa: BLE001
            partial = True
            partial_reason = str(exc)[:180]
            print(f"[DouyinAll] issues failed: {exc}", flush=True)
    finally:
        _close_pw(pw, context)

    client.ingest_douyin_products(
        {
            "job_id": job_id,
            "store_id": store_id,
            "source_url": product_source,
            "products": products,
        }
    )

    _start, _end, day_list = _orders_window_24h()
    by_day: dict[str, list[dict[str, Any]]] = {d: [] for d in day_list}
    for row in orders:
        day = str(row.get("report_day") or "").strip()
        if day in by_day:
            by_day[day].append(row)
    days_payload = [
        {"replace_day": day, "orders": by_day.get(day, [])}
        for day in day_list
    ]
    client.ingest_douyin_orders(
        {
            "job_id": job_id,
            "store_id": store_id,
            "source_url": order_source,
            "days": days_payload,
            "window_start": _start.strftime("%Y-%m-%d %H:%M:%S"),
            "window_end": _end.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )

    client.ingest_douyin_issues(
        {
            "job_id": job_id,
            "store_id": store_id,
            "issues": issues,
            "partial": partial,
            "partial_reason": partial_reason,
            "message": f"已同步内容预警 {len(issues)} 条",
        }
    )

    total_orders = sum(len(d["orders"]) for d in days_payload)
    return {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "scope": "all",
        "orders_count": total_orders,
        "products_count": len(products),
        "issues_count": len(issues),
        "partial": partial,
        "message": (
            f"已同步商品 {len(products)} 条、订单 {total_orders} 条、内容预警 {len(issues)} 条"
        ),
        "synced_at": datetime.now(SHANGHAI).isoformat(),
        "source_url": product_source,
    }


_COMPASS_INDEX_SELECTED = ",".join(
    [
        "pay_amt",
        "pay_cnt",
        "pay_ucnt",
        "income_amt",
        "per_usr_pay_amt",
        "product_show_ucnt",
        "product_show_cnt",
        "product_click_ucnt",
        "product_click_cnt",
        "product_show_click_cnt_ratio",
        "product_click_pay_cnt_ratio",
        "settlement_amt_pay_time",
        "rfndsuc_amt",
        "refund_amt_rate",
        "rfndsuc_amt_pay_time",
        "refund_amt",
    ]
)


def _compass_unit_value(node: Any) -> tuple[float | None, int | None]:
    """Return (numeric_value, unit) from compass index cell."""
    if not isinstance(node, dict):
        return None, None
    candidates = [
        node.get("index_value"),
        node.get("index_values"),
        node,
    ]
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        value_node = cand.get("value")
        if isinstance(value_node, dict) and "value" in value_node:
            try:
                unit = value_node.get("unit")
                unit_i = int(unit) if unit is not None else None
                return float(value_node.get("value")), unit_i
            except Exception:
                continue
        if "value" in cand and isinstance(cand.get("value"), (int, float)):
            try:
                unit = cand.get("unit")
                unit_i = int(unit) if unit is not None else None
                return float(cand.get("value")), unit_i
            except Exception:
                continue
    return None, None


def _compass_display_value(node: Any, *, as_percent: bool = False) -> float | None:
    raw, unit = _compass_unit_value(node)
    if raw is None:
        return None
    # unit=3 amount fen; unit=4 ratio 0-1; unit=5 count/score
    if unit == 3:
        return round(raw / 100.0, 2)
    if unit == 4 or as_percent:
        # store percent 0-100 for UI
        if abs(raw) <= 1.5:
            return round(raw * 100.0, 2)
        return round(raw, 2)
    return raw


def _compass_core_row(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return {}
    module = data.get("module_data") if isinstance(data.get("module_data"), dict) else {}
    card = (
        (module.get("homepage_core_index") or {}).get("compass_general_multi_index_card_value")
        if isinstance(module.get("homepage_core_index"), dict)
        else {}
    )
    if not isinstance(card, dict):
        return {}
    rows = card.get("data")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return rows[0]
    return {}


def _map_compass_exp(payload: dict[str, Any]) -> dict[str, float | None]:
    out: dict[str, float | None] = {
        "exp_score": None,
        "exp_product": None,
        "exp_service": None,
        "exp_logistics": None,
    }
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or not data:
        return out
    root = data[0] if isinstance(data[0], dict) else {}
    cell = root.get("cell_info") if isinstance(root.get("cell_info"), dict) else {}
    exp = cell.get("exp_score") if isinstance(cell.get("exp_score"), dict) else {}
    out["exp_score"] = _compass_display_value(
        exp.get("exp_score_index_value") or exp.get("exp_score_index_values")
    )
    detail = cell.get("exp_score_detail") if isinstance(cell.get("exp_score_detail"), dict) else {}
    children_wrap = (
        detail.get("exp_score_detail_children")
        if isinstance(detail.get("exp_score_detail_children"), dict)
        else {}
    )
    children = children_wrap.get("children") if isinstance(children_wrap.get("children"), list) else []
    scores: list[float] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        cinfo = child.get("cell_info") if isinstance(child.get("cell_info"), dict) else {}
        cexp = cinfo.get("children_exp") if isinstance(cinfo.get("children_exp"), dict) else {}
        val = _compass_display_value(cexp.get("exp_value"))
        if val is not None:
            scores.append(float(val))
    if len(scores) >= 1:
        out["exp_product"] = scores[0]
    if len(scores) >= 2:
        out["exp_service"] = scores[1]
    if len(scores) >= 3:
        out["exp_logistics"] = scores[2]
    return out


def _parse_carriers_from_text(text: str) -> list[dict[str, Any]]:
    """Best-effort parse 按载体 block from page text."""
    if not text:
        return []
    labels = ("商品卡", "直播", "短视频", "图文", "其他")
    carriers: list[dict[str, Any]] = []
    for label in labels:
        # e.g. 商品卡\n¥1,043.73\n59.32%
        pat = re.compile(
            rf"{re.escape(label)}\s*¥?\s*([0-9,]+(?:\.[0-9]+)?|-)\s*([0-9]+(?:\.[0-9]+)?)?\s*%?",
            re.M,
        )
        m = pat.search(text.replace(",", ""))
        if not m:
            continue
        amt_s = m.group(1)
        if amt_s == "-":
            continue
        try:
            amt = float(amt_s)
        except Exception:
            continue
        ratio = None
        if m.group(2):
            try:
                ratio = float(m.group(2))
            except Exception:
                ratio = None
        carriers.append({"name": label, "pay_amt": amt, "ratio": ratio})
    return carriers


def _page_fetch_json(page, path: str, params: dict[str, str]) -> dict[str, Any]:
    result = page.evaluate(
        """async ({ path, params }) => {
          const q = new URLSearchParams(params || {});
          const r = await fetch(path + '?' + q.toString(), { credentials: 'include' });
          const j = await r.json();
          return { status: r.status, body: j };
        }""",
        {"path": path, "params": params},
    )
    if not isinstance(result, dict):
        raise RuntimeError("罗盘接口返回异常")
    if int(result.get("status") or 0) >= 400:
        raise RuntimeError(f"罗盘接口 HTTP {result.get('status')}")
    body = result.get("body")
    if not isinstance(body, dict):
        raise RuntimeError("罗盘接口非 JSON 对象")
    st = body.get("st", body.get("code"))
    if st not in (0, "0", None, ""):
        raise RuntimeError(f"罗盘接口 st={st} msg={body.get('msg') or body.get('message')}")
    return body


def _page_fetch_json_batch(
    page,
    path: str,
    params_list: list[dict[str, str]],
) -> list[tuple[dict[str, Any] | None, str]]:
    """Fetch the same API path with several param sets in one in-page round trip.

    Returns ``(body, error)`` pairs in input order. Requests run in parallel
    inside the page, so the number of Playwright round trips stays constant
    regardless of how many date windows are requested.
    """
    result = page.evaluate(
        """async ({ path, paramsList }) => {
          const out = await Promise.all((paramsList || []).map(async (params) => {
            const q = new URLSearchParams();
            Object.entries(params || {}).forEach(([k, v]) => {
              if (v === undefined || v === null) return;
              q.set(k, String(v));
            });
            try {
              const r = await fetch(path + '?' + q.toString(), { credentials: 'include' });
              let body = null;
              try { body = await r.json(); } catch (e) { body = { parse_error: String(e) }; }
              return { status: r.status, body };
            } catch (e) {
              return { status: 0, body: { fetch_error: String(e) } };
            }
          }));
          return out;
        }""",
        {"path": path, "paramsList": params_list},
    )
    if not isinstance(result, list):
        raise RuntimeError("罗盘接口批量返回异常")
    pairs: list[tuple[dict[str, Any] | None, str]] = []
    for item in result:
        if not isinstance(item, dict):
            pairs.append((None, "返回项异常"))
            continue
        status = int(item.get("status") or 0)
        body = item.get("body")
        if status >= 400:
            pairs.append((None, f"罗盘接口 HTTP {status}"))
            continue
        if not isinstance(body, dict):
            pairs.append((None, "罗盘接口非 JSON 对象"))
            continue
        st = body.get("st", body.get("code"))
        if st not in (0, "0", None, ""):
            pairs.append((None, f"罗盘接口 st={st} msg={body.get('msg') or body.get('message')}"))
            continue
        pairs.append((body, ""))
    return pairs


def _compass_date_window(date_type: int) -> tuple[str, str, str]:
    """Return (begin_date, end_date, report_day) for compass date_type."""
    today = datetime.now(SHANGHAI).date()
    yesterday = today - timedelta(days=1)
    if int(date_type) == 1:
        begin = end = today
    elif int(date_type) == 20:
        begin = end = yesterday
    elif int(date_type) == 21:
        begin = yesterday - timedelta(days=6)
        end = yesterday
    elif int(date_type) == 23:
        begin = yesterday - timedelta(days=29)
        end = yesterday
    else:
        begin = end = today
    fmt = lambda d: d.strftime("%Y/%m/%d 00:00:00")
    return fmt(begin), fmt(end), today.strftime("%Y-%m-%d")


def _build_compass_snapshot_from_core(
    *,
    core_body: dict[str, Any],
    summary_body: dict[str, Any],
    exp_map: dict[str, Any],
    carriers: list[dict[str, Any]],
    date_type: int,
    date_label: str,
    begin_date: str,
    end_date: str,
    report_day: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    row = _compass_core_row(core_body)
    if not row:
        raise RuntimeError(f"DY_COMPASS_SOURCE_UNAVAILABLE: 核心指标为空 date_type={date_type}")

    metrics: dict[str, Any] = {}
    for key, node in row.items():
        val = _compass_display_value(
            node,
            as_percent=("ratio" in key or "rate" in key),
        )
        if val is not None:
            metrics[key] = val
        if isinstance(node, dict):
            iv = node.get("index_value")
            if isinstance(iv, dict) and isinstance(iv.get("last_value"), dict):
                last_v, last_u = _compass_unit_value({"value": iv.get("last_value")})
                if last_v is not None:
                    if last_u == 3:
                        metrics[f"{key}__last"] = round(last_v / 100.0, 2)
                    elif last_u == 4 and abs(last_v) <= 1.5:
                        metrics[f"{key}__last"] = round(last_v * 100.0, 2)
                    else:
                        metrics[f"{key}__last"] = last_v

    snapshot = {
        "report_day": report_day,
        "date_type": int(date_type),
        "date_label": date_label,
        "begin_date": begin_date,
        "end_date": end_date,
        "pay_amt": metrics.get("pay_amt"),
        "pay_cnt": metrics.get("pay_cnt"),
        "pay_ucnt": metrics.get("pay_ucnt"),
        "income_amt": metrics.get("income_amt"),
        "per_usr_pay_amt": metrics.get("per_usr_pay_amt"),
        "product_show_ucnt": metrics.get("product_show_ucnt"),
        "product_show_cnt": metrics.get("product_show_cnt"),
        "product_click_ucnt": metrics.get("product_click_ucnt"),
        "product_click_cnt": metrics.get("product_click_cnt"),
        "show_click_rate": metrics.get("product_show_click_cnt_ratio"),
        "click_pay_rate": metrics.get("product_click_pay_cnt_ratio"),
        "settlement_amt": metrics.get("settlement_amt_pay_time"),
        "refund_amt": metrics.get("rfndsuc_amt")
        if metrics.get("rfndsuc_amt") is not None
        else metrics.get("refund_amt"),
        "refund_rate": metrics.get("refund_amt_rate"),
        "exp_score": exp_map.get("exp_score"),
        "exp_product": exp_map.get("exp_product"),
        "exp_service": exp_map.get("exp_service"),
        "exp_logistics": exp_map.get("exp_logistics"),
        "carriers": carriers if int(date_type) == 1 else [],
        "metrics": metrics,
        "source_url": f"https://compass.jinritemai.com/shop?dateType={int(date_type)}",
    }
    raw = {
        "core_index_v3": core_body,
        "summary_core_index_v3": summary_body,
        "date_type": int(date_type),
        "begin_date": begin_date,
        "end_date": end_date,
    }
    return snapshot, raw


def fetch_compass_snapshots(page) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Fetch 实时 / 近1天 / 近7天 / 近30天 core_index snapshots."""
    print(f"[DouyinCompass] goto {DOUYIN_COMPASS_PAGE}", flush=True)
    try:
        page.goto(DOUYIN_COMPASS_PAGE, wait_until="domcontentloaded", timeout=90_000)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"DY_COMPASS_SOURCE_UNAVAILABLE: 无法打开罗盘首页: {exc}") from exc
    time.sleep(0.8)

    exp_body: dict[str, Any] = {}
    try:
        exp_body = _page_fetch_json(
            page,
            DOUYIN_COMPASS_EXP_API,
            {"grow_score_usable": "true"},
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[DouyinCompass] exp_score failed: {exc}", flush=True)
    exp_map = _map_compass_exp(exp_body)

    page_text = ""
    try:
        page_text = str(page.evaluate("() => document.body ? document.body.innerText : ''") or "")
    except Exception:
        page_text = ""
    carriers = _parse_carriers_from_text(page_text)

    core_params_list: list[dict[str, str]] = []
    summary_params_list: list[dict[str, str]] = []
    for cfg in DOUYIN_COMPASS_DATE_TYPES:
        dt = int(cfg["date_type"])
        begin_date, end_date, report_day = _compass_date_window(dt)
        core_params_list.append({
            "begin_date": begin_date,
            "end_date": end_date,
            "date_type": str(dt),
            "activity_id": "",
            "index_selected": _COMPASS_INDEX_SELECTED,
        })
        summary_params_list.append({
            "begin_date": begin_date,
            "end_date": end_date,
            "date_type": str(dt),
            "activity_id": "",
            "select_ad_expense_ratio": "ad_costed",
        })

    # One round trip per endpoint instead of one per date window.
    core_pairs = _call_with_retry(
        lambda: _page_fetch_json_batch(page, DOUYIN_COMPASS_CORE_API, core_params_list),
        label="compass core batch",
    )
    summary_pairs = _call_with_retry(
        lambda: _page_fetch_json_batch(page, DOUYIN_COMPASS_SUMMARY_API, summary_params_list),
        retries=0,
        label="compass summary batch",
    )

    out: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for idx, cfg in enumerate(DOUYIN_COMPASS_DATE_TYPES):
        dt = int(cfg["date_type"])
        label = str(cfg["label"])
        begin_date, end_date, report_day = _compass_date_window(dt)
        core_body, core_err = core_pairs[idx] if idx < len(core_pairs) else (None, "批量结果缺失")
        if core_body is None:
            raise RuntimeError(
                f"DY_COMPASS_SOURCE_UNAVAILABLE: 核心指标失败 date_type={dt}: {core_err}"
            )

        summary_body, summary_err = (
            summary_pairs[idx] if idx < len(summary_pairs) else (None, "批量结果缺失")
        )
        if summary_body is None:
            print(
                f"[DouyinCompass] summary optional failed date_type={dt}: {summary_err}",
                flush=True,
            )

        snapshot, raw = _build_compass_snapshot_from_core(
            core_body=core_body,
            summary_body=summary_body or {},
            exp_map=exp_map,
            carriers=carriers,
            date_type=dt,
            date_label=label,
            begin_date=begin_date,
            end_date=end_date,
            report_day=report_day,
        )
        if dt == 1:
            raw["prof_exp_score"] = exp_body
        print(
            f"[DouyinCompass] {label} date_type={dt} pay_amt={snapshot.get('pay_amt')} "
            f"pay_cnt={snapshot.get('pay_cnt')}",
            flush=True,
        )
        out.append((snapshot, raw))
    if not out:
        raise RuntimeError("DY_COMPASS_SOURCE_UNAVAILABLE: 未拉到任何时间档")
    return out


def fetch_compass_snapshot(page) -> tuple[dict[str, Any], dict[str, Any]]:
    """Backward-compatible: fetch realtime (date_type=1) only. """
    snapshots = fetch_compass_snapshots(page)
    for snap, raw in snapshots:
        if int(snap.get("date_type") or 0) == 1:
            return snap, raw
    if not snapshots:
        raise RuntimeError("DY_COMPASS_SOURCE_UNAVAILABLE: 未拉到罗盘快照")
    return snapshots[0]


def run_compass_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    job_id = str(payload.get("job_id") or "")
    store_id = str(payload.get("store_id") or "").strip()

    if not DOUYIN_COMPASS_XHR_READY:
        raise RuntimeError("DY_COMPASS_SOURCE_UNAVAILABLE: 罗盘接口尚未就绪")

    store_id = _resolve_store_id(client, tenant_id, store_id)
    if not store_id:
        store_id = "default"

    pw = context = page = None
    try:
        pw, context, page = _launch(
            tenant_id,
            headless=sync_headless_enabled(),
            force_navigate=True,
            store_id=store_id,
        )
        if not _looks_logged_in(page, context):
            if sync_headless_enabled():
                raise RuntimeError(
                    "DY_NOT_LOGGED_IN: 抖音未登录（无头模式不弹窗）。请先点「打开登录」完成登录后再同步"
                )
            logged_in, page = _wait_until_logged_in(
                page,
                context,
                timeout_seconds=300,
                label="compass_sync",
            )
            if not logged_in:
                raise RuntimeError("DY_NOT_LOGGED_IN: 抖音商家后台未登录，请打开登录窗口完成登录")
        pairs = fetch_compass_snapshots(page)
    finally:
        _close_pw(pw, context)

    labels: list[str] = []
    realtime_pay_amt = None
    realtime_pay_cnt = None
    for snapshot, raw in pairs:
        dt = int(snapshot.get("date_type") or 1)
        label = str(snapshot.get("date_label") or dt)
        labels.append(label)
        if dt == 1:
            realtime_pay_amt = snapshot.get("pay_amt")
            realtime_pay_cnt = snapshot.get("pay_cnt")
        ingest_body = {
            "job_id": job_id,
            "store_id": store_id,
            "date_type": dt,
            "report_day": snapshot.get("report_day"),
            "snapshot": snapshot,
            "raw": raw,
            "source_url": snapshot.get("source_url") or DOUYIN_COMPASS_PAGE,
            "message": f"已同步抖店罗盘（{label}）",
        }
        client.ingest_douyin_compass(ingest_body)

    message = f"已同步抖店罗盘（{' / '.join(labels)}）"
    return {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "scope": "compass",
        "orders_count": 0,
        "products_count": 0,
        "issues_count": 0,
        "partial": False,
        "message": message,
        "synced_at": datetime.now(SHANGHAI).isoformat(),
        "source_url": DOUYIN_COMPASS_PAGE,
        "pay_amt": realtime_pay_amt,
        "pay_cnt": realtime_pay_cnt,
        "date_types": [int(s.get("date_type") or 0) for s, _ in pairs],
        "count": len(pairs),
    }


def _page_post_json(page, path: str, body: dict[str, Any]) -> dict[str, Any]:
    result = page.evaluate(
        """async ({ path, body }) => {
          const r = await fetch(path, {
            method: 'POST',
            credentials: 'include',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify(body || {}),
          });
          let json = null;
          try { json = await r.json(); } catch (e) {}
          return { status: r.status, body: json };
        }""",
        {"path": path, "body": body},
    )
    if not isinstance(result, dict):
        raise RuntimeError("商机接口返回异常")
    if int(result.get("status") or 0) >= 400:
        raise RuntimeError(f"商机接口 HTTP {result.get('status')}")
    payload = result.get("body")
    if not isinstance(payload, dict):
        raise RuntimeError("商机接口非 JSON 对象")
    return payload


def _page_get_json(page, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    result = page.evaluate(
        """async ({ path, params }) => {
          const q = new URLSearchParams();
          Object.entries(params || {}).forEach(([k, v]) => {
            if (v === undefined || v === null) return;
            q.set(k, String(v));
          });
          const url = q.toString() ? (path + '?' + q.toString()) : path;
          const r = await fetch(url, { credentials: 'include' });
          let json = null;
          try { json = await r.json(); } catch (e) {}
          return { status: r.status, body: json };
        }""",
        {"path": path, "params": params or {}},
    )
    if not isinstance(result, dict) or int(result.get("status") or 0) >= 400:
        raise RuntimeError(f"商机类目接口失败: {result}")
    body = result.get("body")
    if not isinstance(body, dict):
        raise RuntimeError("商机类目接口非 JSON")
    return body


def _walk_category_tree(nodes: list[Any], needle: str, path: list[dict[str, Any]] | None = None) -> list[dict[str, Any]] | None:
    path = path or []
    needle_l = (needle or "").strip().lower()
    if not needle_l:
        return None
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        label = str(node.get("label") or node.get("name") or "").strip()
        value = node.get("value") if node.get("value") is not None else node.get("id")
        cur = {"label": label, "value": value}
        next_path = path + [cur]
        if label and needle_l in label.lower():
            return next_path
        children = node.get("children")
        if isinstance(children, list) and children:
            hit = _walk_category_tree(children, needle, next_path)
            if hit:
                return hit
    return None


def _categories_condition_from_path(path: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [p.get("value") for p in path if p.get("value") is not None]
    obj: dict[str, Any] = {}
    names = ["first_cid", "second_cid", "third_cid", "fourth_cid"]
    for i, cid in enumerate(ids[:4]):
        try:
            obj[names[i]] = int(cid)
        except Exception:
            obj[names[i]] = cid
    out: dict[str, Any] = {"categories": [obj]} if obj else {}
    if ids:
        try:
            out["leaf_cid_list"] = [int(ids[-1])]
        except Exception:
            out["leaf_cid_list"] = [ids[-1]]
    return out


def _map_opportunity_item(item: dict[str, Any], rank_no: int, detail: dict[str, Any] | None) -> dict[str, Any]:
    detail_body = detail or {}
    clue = item.get("clue_detail") if isinstance(item.get("clue_detail"), dict) else {}
    indicator = item.get("clue_indicator") if isinstance(item.get("clue_indicator"), dict) else {}
    card = item.get("query_clue_card_info") if isinstance(item.get("query_clue_card_info"), dict) else {}
    labels = []
    for lab in clue.get("clue_label_list") or []:
        if isinstance(lab, dict) and lab.get("label_name"):
            labels.append(str(lab.get("label_name")))
    for profit in clue.get("profit_info_list") or []:
        if isinstance(profit, dict) and profit.get("profit_name"):
            labels.append(str(profit.get("profit_name")))
    path = clue.get("category_path")
    if isinstance(path, list):
        category_path = "/".join(str(x) for x in path if x)
    else:
        category_path = str(path or clue.get("category_name") or "")
    # 商机中心列表无独立「当日/7天/30天」切换；主口径 + 7日销量 + 30日增速一并入库展示
    period_metrics = {
        "day": {
            "label": "当日相关",
            "search_popularity": card.get("search_popularity"),
            "pay_order_cnt": indicator.get("pay_order_cnt"),
            "pay_order_cnt_range": indicator.get("pay_order_cnt_range"),
            "note": "卡片搜索热度 / 成交单量（接口无独立当日榜）",
        },
        "d7": {
            "label": "近7天",
            "seven_day_sales": indicator.get("seven_day_sales"),
        },
        "d30": {
            "label": "近30天",
            "search_pv_cnt": indicator.get("search_pv_cnt"),
            "search_pv_cnt_range": indicator.get("search_pv_cnt_range") or indicator.get("demand_heat_range"),
            "search_pv_cnt_30d_rate": indicator.get("search_pv_cnt_30d_rate"),
            "pay_amount_ind": indicator.get("pay_amount_ind"),
            "pay_amount_ind_range": indicator.get("pay_amount_ind_range"),
            "pay_amount_ind_30d_rate": indicator.get("pay_amount_ind_30d_rate"),
            "demand_supply_rate": indicator.get("demand_supply_rate"),
            "demand_supply_rate_30d_rate": indicator.get("demand_supply_rate_30d_rate"),
        },
    }
    overview = {
        "from_list": {
            "clue_indicator": indicator,
            "query_clue_card_info": card,
            "clue_label_list": clue.get("clue_label_list") or [],
            "profit_info_list": clue.get("profit_info_list") or [],
        },
        "period_metrics": period_metrics,
        "detail": detail_body.get("data") if isinstance(detail_body.get("data"), dict) else detail_body,
    }
    return {
        "rank_no": rank_no,
        "clue_id": str(clue.get("clue_id") or ""),
        "product_name": str(clue.get("name") or ""),
        "main_image": str(clue.get("product_pic_url") or ""),
        "category_path": category_path,
        "category_name": str(clue.get("category_name") or category_path),
        "category_id": str(clue.get("category_id") or clue.get("third_cid") or clue.get("second_cid") or ""),
        "price_min": clue.get("price_min"),
        "price_max": clue.get("price_max"),
        "search_heat": indicator.get("search_heat"),
        "search_pv_range": indicator.get("search_pv_cnt_range") or indicator.get("demand_heat_range"),
        "search_pv_cnt": indicator.get("search_pv_cnt"),
        "search_pv_30d_rate": indicator.get("search_pv_cnt_30d_rate"),
        "seven_day_sales": indicator.get("seven_day_sales"),
        "search_popularity": card.get("search_popularity"),
        "pay_order_cnt": indicator.get("pay_order_cnt"),
        "pay_order_cnt_range": indicator.get("pay_order_cnt_range"),
        "pay_growth_rate": indicator.get("pay_amount_ind_30d_rate"),
        "pay_amt": indicator.get("pay_amount_ind"),
        "pay_amt_range": indicator.get("pay_amount_ind_range"),
        "demand_supply_rate": indicator.get("demand_supply_rate"),
        "period_metrics": period_metrics,
        "labels": labels,
        "overview": overview,
        "raw": {"list_item": item, "detail": detail_body},
    }


def _normalize_opportunity_pool(pool: str) -> str:
    raw = (pool or "").strip().lower()
    aliases = {
        "": "potential",
        "potential": "potential",
        "potential_hot": "potential",
        "hot_product": "potential",
        "recommend": "potential",
        "跟潜力爆品": "potential",
        "hot_words": "hot_words",
        "hotwords": "hot_words",
        "words": "hot_words",
        "追抖音热词": "hot_words",
    }
    return aliases.get(raw, raw if raw in DOUYIN_OPPORTUNITY_POOLS else "potential")


def _normalize_opportunity_sort(sort_field: str, *, pool: str) -> str:
    raw = (sort_field or "").strip().upper()
    aliases = {
        "": "",
        "RECOMMEND": "MATCH_DEGREE",
        "MATCH": "MATCH_DEGREE",
        "为你推荐": "MATCH_DEGREE",
        "TRADING": "TRADING_AMOUNT",
        "成交高": "TRADING_AMOUNT",
        "GROWTH": "PAY_AMOUNT_RATE",
        "增速快": "PAY_AMOUNT_RATE",
        "COMPETE": "DEMAND_SUPPLY_RATE",
        "竞争小": "DEMAND_SUPPLY_RATE",
    }
    if raw in aliases:
        raw = aliases[raw]
    if raw in DOUYIN_OPPORTUNITY_SORTS:
        return raw
    return str(DOUYIN_OPPORTUNITY_POOLS.get(pool, {}).get("default_sort") or "MATCH_DEGREE")


def _opportunity_pool_label(pool: str, sort_field: str) -> str:
    pool_label = str(DOUYIN_OPPORTUNITY_POOLS.get(pool, {}).get("label") or pool)
    sort_label = DOUYIN_OPPORTUNITY_SORTS.get(sort_field) or sort_field
    return f"{pool_label}·{sort_label}"


def fetch_opportunity_top100(
    page,
    *,
    category_query: str = "",
    category_id: str = "",
    pool: str = "potential",
    sort_field: str = "",
    limit: int = 100,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pool_key = _normalize_opportunity_pool(pool)
    sort_key = _normalize_opportunity_sort(sort_field, pool=pool_key)
    pool_cfg = DOUYIN_OPPORTUNITY_POOLS[pool_key]
    clue_type_new = int(pool_cfg["clue_type_new"])
    pool_title = _opportunity_pool_label(pool_key, sort_key)

    print(f"[DouyinOpp] goto {DOUYIN_OPPORTUNITY_PAGE} pool={pool_key} sort={sort_key}", flush=True)
    try:
        page.goto(DOUYIN_OPPORTUNITY_PAGE, wait_until="domcontentloaded", timeout=90_000)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"DY_OPPORTUNITY_SOURCE_UNAVAILABLE: 无法打开商机中心: {exc}") from exc
    time.sleep(0.8)

    condition: dict[str, Any] = {
        "hit_clue_label_ext": True,
        "show_new_supply_link": True,
        "include_hot_sales_products": True,
        "sort": {"sort_direction": 1, "sort_field": sort_key},
    }
    meta: dict[str, Any] = {
        "is_default_category": True,
        "category_query": (category_query or "").strip(),
        "category_id": (category_id or "").strip(),
        "category_name": f"{pool_title}(默认)",
        "category_key": f"pool:{pool_key}|sort:{sort_key}|default",
        "pool": pool_key,
        "sort_field": sort_key,
        "source_url": DOUYIN_OPPORTUNITY_PAGE,
    }

    resolved_path: list[dict[str, Any]] | None = None
    if meta["category_id"]:
        try:
            leaf = int(meta["category_id"])
            condition["leaf_cid_list"] = [leaf]
            meta["is_default_category"] = False
            meta["category_key"] = f"pool:{pool_key}|sort:{sort_key}|leaf:{leaf}"
            meta["category_name"] = f"{pool_title}·{meta['category_query'] or leaf}"
        except Exception:
            pass
    elif meta["category_query"]:
        try:
            cats = _page_get_json(
                page,
                DOUYIN_OPPORTUNITY_CATEGORY_API,
                {"clue_type_new": clue_type_new, "source_channel_code": ""},
            )
            tree = cats.get("data") if isinstance(cats.get("data"), list) else []
            resolved_path = _walk_category_tree(tree, meta["category_query"])
        except Exception as exc:  # noqa: BLE001
            print(f"[DouyinOpp] category tree failed: {exc}", flush=True)
        if resolved_path:
            condition.update(_categories_condition_from_path(resolved_path))
            meta["is_default_category"] = False
            labels = [str(p.get("label") or "") for p in resolved_path]
            path_name = "/".join(x for x in labels if x) or meta["category_query"]
            leaf = resolved_path[-1].get("value")
            meta["category_id"] = str(leaf or "")
            meta["category_name"] = f"{pool_title}·{path_name}"
            meta["category_key"] = (
                f"pool:{pool_key}|sort:{sort_key}|leaf:{leaf}"
                if leaf is not None
                else f"pool:{pool_key}|sort:{sort_key}|q:{meta['category_query']}"
            )
        else:
            raise RuntimeError(
                f"DY_OPPORTUNITY_SOURCE_UNAVAILABLE: 未找到类目「{meta['category_query']}」"
            )

    page_size = 100
    need = max(1, min(100, int(limit or 100)))
    collected: list[dict[str, Any]] = []
    total = None
    for current in range(1, 5):
        if len(collected) >= need:
            break
        body = {
            "condition": condition,
            "clue_type": "",
            "clue_type_new": clue_type_new,
            "page": {"current": current, "page_size": page_size},
            "terminal_type": 0,
            "source": "business_center",
        }
        try:
            if current == 1:
                resp = _call_with_retry(
                    lambda body=body: _page_post_json(page, DOUYIN_OPPORTUNITY_LIST_API, body),
                    label="opportunity list page1",
                )
            else:
                resp = _page_post_json(page, DOUYIN_OPPORTUNITY_LIST_API, body)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"DY_OPPORTUNITY_SOURCE_UNAVAILABLE: 列表失败: {exc}") from exc
        code = resp.get("code", (resp.get("base_resp") or {}).get("status_code"))
        if code not in (0, "0", 200, "200", None, ""):
            raise RuntimeError(f"DY_OPPORTUNITY_SOURCE_UNAVAILABLE: 列表 code={code}")
        rows = resp.get("data")
        if not isinstance(rows, list):
            raise RuntimeError("DY_OPPORTUNITY_SOURCE_UNAVAILABLE: 列表 data 为空")
        if total is None:
            total = resp.get("total")
        collected.extend([r for r in rows if isinstance(r, dict)])
        if len(rows) < page_size:
            break

    collected = collected[:need]
    if not collected:
        raise RuntimeError(f"DY_OPPORTUNITY_SOURCE_UNAVAILABLE: 未拉到{pool_title}商品")

    # Prefetch detail overviews in batches.
    clue_ids = []
    for row in collected:
        cd = row.get("clue_detail") if isinstance(row.get("clue_detail"), dict) else {}
        cid = cd.get("clue_id")
        if cid is not None:
            clue_ids.append(cid)
    details: dict[str, Any] = {}
    batch = 10
    for i in range(0, len(clue_ids), batch):
        chunk = clue_ids[i : i + batch]
        try:
            part = page.evaluate(
                """async ({ path, ids }) => {
                  const out = {};
                  for (const id of ids) {
                    try {
                      const r = await fetch(path, {
                        method: 'POST',
                        credentials: 'include',
                        headers: { 'content-type': 'application/json' },
                        body: JSON.stringify({ clue_id: id, clue_channel: '' }),
                      });
                      out[String(id)] = await r.json();
                    } catch (e) {
                      out[String(id)] = { error: String(e) };
                    }
                  }
                  return out;
                }""",
                {"path": DOUYIN_OPPORTUNITY_DETAIL_API, "ids": chunk},
            )
            if isinstance(part, dict):
                details.update(part)
        except Exception as exc:  # noqa: BLE001
            print(f"[DouyinOpp] detail batch failed: {exc}", flush=True)

    products: list[dict[str, Any]] = []
    for idx, row in enumerate(collected, start=1):
        cd = row.get("clue_detail") if isinstance(row.get("clue_detail"), dict) else {}
        cid = str(cd.get("clue_id") or "")
        products.append(_map_opportunity_item(row, idx, details.get(cid)))

    if meta["is_default_category"]:
        meta["category_name"] = pool_title

    meta["total_available"] = total
    print(
        f"[DouyinOpp] synced={len(products)} pool={pool_key} sort={sort_key} "
        f"category={meta.get('category_name')}",
        flush=True,
    )
    return products, meta


def run_opportunity_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    job_id = str(payload.get("job_id") or "")
    store_id = str(payload.get("store_id") or "").strip()
    category_query = str(payload.get("category_query") or payload.get("categoryQuery") or "").strip()
    category_id = str(payload.get("category_id") or payload.get("categoryId") or "").strip()
    pool = str(payload.get("pool") or payload.get("opportunity_pool") or "potential").strip()
    sort_field = str(payload.get("sort_field") or payload.get("sortField") or "").strip()

    if not DOUYIN_OPPORTUNITY_XHR_READY:
        raise RuntimeError("DY_OPPORTUNITY_SOURCE_UNAVAILABLE: 商机接口尚未就绪")

    store_id = _resolve_store_id(client, tenant_id, store_id)
    if not store_id:
        store_id = "default"

    pw = context = page = None
    try:
        pw, context, page = _launch(
            tenant_id,
            headless=sync_headless_enabled(),
            force_navigate=True,
            store_id=store_id,
        )
        if not _looks_logged_in(page, context):
            if sync_headless_enabled():
                raise RuntimeError(
                    "DY_NOT_LOGGED_IN: 抖音未登录（无头模式不弹窗）。请先点「打开登录」完成登录后再同步"
                )
            logged_in, page = _wait_until_logged_in(
                page,
                context,
                timeout_seconds=300,
                label="opportunity_sync",
            )
            if not logged_in:
                raise RuntimeError("DY_NOT_LOGGED_IN: 抖音商家后台未登录，请打开登录窗口完成登录")
        products, meta = fetch_opportunity_top100(
            page,
            category_query=category_query,
            category_id=category_id,
            pool=pool,
            sort_field=sort_field,
            limit=100,
        )
    finally:
        _close_pw(pw, context)

    ingest_body = {
        "job_id": job_id,
        "store_id": store_id,
        "category_key": meta.get("category_key"),
        "category_id": meta.get("category_id"),
        "category_name": meta.get("category_name"),
        "category_query": meta.get("category_query"),
        "is_default_category": bool(meta.get("is_default_category")),
        "pool": meta.get("pool"),
        "sort_field": meta.get("sort_field"),
        "source_url": meta.get("source_url") or DOUYIN_OPPORTUNITY_PAGE,
        "products": products,
        "message": f"已同步商机中心{meta.get('category_name')} Top{len(products)}",
    }
    client.ingest_douyin_opportunity(ingest_body)
    return {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "scope": "opportunity",
        "orders_count": 0,
        "products_count": len(products),
        "issues_count": 0,
        "partial": False,
        "message": ingest_body["message"],
        "synced_at": datetime.now(SHANGHAI).isoformat(),
        "source_url": DOUYIN_OPPORTUNITY_PAGE,
        "category_key": meta.get("category_key"),
        "category_name": meta.get("category_name"),
        "pool": meta.get("pool"),
        "sort_field": meta.get("sort_field"),
        "count": len(products),
    }


# Optional re-export for callers that import sync runners from douyin_tasks.
try:
    from agent.douyin_compass_rank import run_compass_product_rank_sync  # noqa: F401
except Exception:  # pragma: no cover
    run_compass_product_rank_sync = None  # type: ignore[misc, assignment]
