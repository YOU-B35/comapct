"""Pinduoduo (拼多多) Agent tasks: login / probe / orders / products / compass sync.

复刻 ``douyin_tasks`` 接入模式：Playwright 持久化 Profile + 卖家后台 XHR。
数据 scope：订单（按 date_window 时间段分）/ 商品 / 经营罗盘。

<b>当前为 probe-就绪骨架</b>：登录/会话探测/浏览器生命周期已可用，
但 ``PDD_ORDERS_XHR_READY`` / ``PDD_PRODUCTS_XHR_READY`` / ``PDD_COMPASS_XHR_READY``
默认 ``False``——需用真实账号在 mms.pinduoduo.com 完成 Day0 probe，
抓出订单/商品/罗盘三类 XHR 的 URL/参数/响应结构，固化到下面对应常量与
``fetch_*_via_xhr`` 实现后，三端数据流即可跑通。
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.browser.pdd_context import (
    PDD_SELLER_HOME,
    close_pdd_profile_browsers,
    ensure_pdd_home_page,
    install_pdd_only_tab_guard,
    launch_pdd_persistent_context,
    sanitize_profile_startup_for_pdd,
)
from app.session_scope import normalize_session_key, resolve_platform_profile_dir

# ============================================================================
# Day0 probe 冻结标记（账号到位 probe 后改 True 并填下方 XHR 常量）
# ============================================================================
PDD_ORDERS_XHR_READY = False
PDD_PRODUCTS_XHR_READY = False
PDD_COMPASS_XHR_READY = False

# 本地开发 Mock 模式开关（生产环境改为 False）
_MOCK_ORDERS_ENABLED = True
_MOCK_PRODUCTS_ENABLED = True
_MOCK_COMPASS_ENABLED = True

# TODO(probe): 拼多多商家后台订单列表 XHR（mms.pinduoduo.com 下，待 probe 填入）
PDD_ORDER_LIST_PAGE = "https://mms.pinduoduo.com/od/index.html"  # 占位，待 probe 校正
PDD_ORDER_LIST_API = ""  # TODO(probe): 订单列表 XHR URL

# TODO(probe): 商品列表 XHR
PDD_PRODUCT_LIST_PAGE = "https://mms.pinduoduo.com/goods/goods_list.html"  # 占位
PDD_PRODUCT_LIST_API = ""  # TODO(probe)

# TODO(probe): 经营罗盘 XHR（拼多多数据中心）
PDD_COMPASS_PAGE = "https://mms.pinduoduo.com/data/index.html"  # 占位
PDD_COMPASS_CORE_API = ""  # TODO(probe)
PDD_COMPASS_DATE_TYPES: list[dict[str, Any]] = [
    {"date_type": 1, "label": "实时", "window": "realtime"},
    {"date_type": 20, "label": "近1天", "window": "d1"},
    {"date_type": 21, "label": "近7天", "window": "d7"},
    {"date_type": 23, "label": "近30天", "window": "d30"},
]

# 拼多多登录态 cookie 标记（probe 后可补充；先用 PASS_ID/ruipk 等常见）
_AUTH_COOKIE_MARKERS = (
    "PASS_ID",
    "ruipk",
    "ruidp",
    "rpcc_id",
    "pdd_user_id",
    "pdd_user_uid",
    "pdd_cookie",
    "J-sessionid",
)

_LOGIN_CTA_MARKERS = (
    "扫码登录",
    "手机号登录",
    "请登录",
    "验证码登录",
    "登录拼多多",
    "立即登录",
    "账号登录",
)

ROOT = Path(__file__).resolve().parents[1]
SHANGHAI = ZoneInfo("Asia/Shanghai")


def profile_dir(tenant_id: int, store_id: str | None = None) -> Path:
    key = normalize_session_key(store_id)
    if key == "default":
        legacy = ROOT / ".pdd-browser-profile" / f"tenant-{int(tenant_id)}"
        legacy.mkdir(parents=True, exist_ok=True)
        return legacy
    path = resolve_platform_profile_dir(
        "pdd",
        tenant_id,
        key,
        root=ROOT / ".pdd-browser-profile",
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_in_clean_thread(fn, *, timeout: float | None = None):
    """Playwright Sync API cannot run when the current thread already has an asyncio loop."""
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        return fut.result(timeout=timeout)


def _pdd_launch_kwargs(*, headless: bool) -> dict[str, Any]:
    import sys

    from app.browser.context import _bundled_chromium_ready, _system_chrome_path
    from app.config import BROWSER_CHANNEL

    kwargs: dict[str, Any] = {
        "headless": headless,
        "viewport": {"width": 1440, "height": 900},
        "locale": "zh-CN",
        "ignore_default_args": ["--enable-automation", "--disable-extensions"],
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
            "--hide-crash-restore-bubble",
            f"--homepage={PDD_SELLER_HOME}",
        ],
    }
    frozen = bool(getattr(sys, "frozen", False))
    if BROWSER_CHANNEL:
        kwargs["channel"] = BROWSER_CHANNEL
    elif frozen and not _bundled_chromium_ready():
        chrome = _system_chrome_path()
        if chrome:
            kwargs["executable_path"] = chrome
        else:
            kwargs["channel"] = "chrome"
    return kwargs


def _has_pdd_profile_lock(profile_dir: Path) -> bool:
    root = Path(profile_dir)
    if (root / "SingletonLock").exists() or (root / "lockfile").exists():
        return True
    return (root / "Default" / "LOCK").exists()


def _close_pw(pw, context) -> None:
    """Graceful close so cookies flush before next sync."""
    try:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
    finally:
        if pw is not None:
            try:
                pw.stop()
            except Exception:
                pass


def _launch(
    tenant_id: int,
    *,
    headless: bool = False,
    force_navigate: bool = True,
    store_id: str | None = None,
):
    from playwright.sync_api import sync_playwright

    user_dir = profile_dir(tenant_id, store_id)
    if _has_pdd_profile_lock(user_dir):
        print("[PddBrowser] stale profile lock present, reclaiming before launch…", flush=True)
        close_pdd_profile_browsers(user_dir)
    sanitize_profile_startup_for_pdd(user_dir, home_url=PDD_SELLER_HOME)
    launch_kwargs = _pdd_launch_kwargs(headless=headless)
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
        context = launch_pdd_persistent_context(
            playwright=None,
            profile_dir=user_dir,
            launch_kwargs=launch_kwargs,
            launch_fn=launch_fn,
            reclaim_fn=lambda: close_pdd_profile_browsers(user_dir),
        )
    except Exception:
        _close_pw(state["pw"], None)
        raise
    install_pdd_only_tab_guard(context)
    page = ensure_pdd_home_page(context, force_navigate=force_navigate)
    return state["pw"], context, page


def _cookie_summary(context) -> str:
    try:
        cookies = context.cookies()
    except Exception:
        return "cookies=unreadable"
    names = sorted({str(c.get("name") or "") for c in cookies if c.get("name")})
    auth_hits = [n for n in names if any(m in n for m in _AUTH_COOKIE_MARKERS)]
    return f"cookies={len(names)} auth={auth_hits[:8] or '-'}"


def _has_auth_cookies(context) -> bool:
    try:
        cookies = context.cookies()
    except Exception:
        return False
    for cookie in cookies:
        name = str(cookie.get("name") or "")
        domain = str(cookie.get("domain") or "").lower()
        if not any(host in domain for host in ("pinduoduo", "pddglobal", "yangkeduo")):
            continue
        if any(marker in name for marker in _AUTH_COOKIE_MARKERS):
            return True
    return False


def _looks_logged_in(page, context=None) -> bool:
    """Require real auth cookies + console chrome; reject login CTA pages."""
    url = (page.url or "").lower()
    if "login" in url or "passport" in url or "sso" in url:
        return False
    if "pinduoduo.com" not in url:
        return False
    try:
        body = page.inner_text("body", timeout=3000)
    except Exception:
        body = ""
    if any(marker in body for marker in _LOGIN_CTA_MARKERS):
        return False
    markers = ("订单", "商品", "售后", "数据", "首页", "拼多多商家")
    hits = sum(1 for m in markers if m in body)
    if hits < 2:
        return False
    if context is not None and not _has_auth_cookies(context):
        return False
    return True


def _wait_until_logged_in(page, context, *, timeout_seconds: int, label: str):
    deadline = time.time() + max(30, int(timeout_seconds))
    last_log = 0.0
    current = page
    while time.time() < deadline:
        try:
            from app.browser.pdd_context import close_foreign_pdd_pages

            close_foreign_pdd_pages(context)
        except Exception:
            pass
        logged_in = _looks_logged_in(current, context)
        now_ts = time.time()
        if logged_in:
            return True, current
        if now_ts - last_log > 5:
            print(
                f"[PddLogin:{label}] waiting login… url={current.url!r} "
                f"{_cookie_summary(context)}",
                flush=True,
            )
            last_log = now_ts
        time.sleep(1.0)
    return _looks_logged_in(current, context), current


# ============================================================================
# 会话探测 / 登录窗口
# ============================================================================

def probe_session(tenant_id: int, store_id: str | None = None) -> dict[str, Any]:
    def _run() -> dict[str, Any]:
        pw = context = page = None
        try:
            pw, context, page = _launch(
                tenant_id, headless=False, force_navigate=True, store_id=store_id,
            )
            time.sleep(1.5)
            logged_in = _looks_logged_in(page, context)
            print(
                f"[PddProbe] tenant={tenant_id} logged_in={logged_in} "
                f"url={page.url!r} {_cookie_summary(context)}",
                flush=True,
            )
            return {
                "tenant_id": tenant_id,
                "ready": logged_in,
                "logged_in": logged_in,
                "requires_auth": not logged_in,
                "profile_busy": False,
                "message": "拼多多已登录" if logged_in else "拼多多未登录，请打开登录窗口完成登录",
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
                tenant_id, headless=False, force_navigate=True, store_id=store_id,
            )
            print(f"[PddLogin] opened {PDD_SELLER_HOME} tenant={tenant_id}", flush=True)
            logged_in, page = _wait_until_logged_in(
                page, context, timeout_seconds=timeout_seconds, label="open_login",
            )
            return {
                "tenant_id": tenant_id,
                "ready": logged_in,
                "logged_in": logged_in,
                "requires_auth": not logged_in,
                "profile_busy": False,
                "message": "拼多多已登录" if logged_in else "登录超时，请重试打开登录窗口",
                "shop_count": 0,
                "shops": [],
            }
        finally:
            _close_pw(pw, context)

    return _run_in_clean_thread(_run, timeout=float(timeout_seconds) + 90)


# ============================================================================
# XHR 抓取（TODO: Day0 probe 后实现）
# ============================================================================

def fetch_orders_via_xhr(page, *, date_window: str = "today") -> tuple[list[dict[str, Any]], str]:
    """抓取订单列表。返回 (rows, source_url)。

    本地开发：返回 Mock 数据
    生产：需完成 Day0 probe 后实现真实 XHR 调用
    """
    if _MOCK_ORDERS_ENABLED:
        from app.mock_pdd import mock_orders_sync_data
        store_id = None  # 从 page 上下文解析，暂时用 None
        return mock_orders_sync_data(0, date_window, store_id)

    # TODO(probe): 账号到位后，在 mms.pinduoduo.com 订单页打开 DevTools Network，
    # 抓出订单列表 XHR 的 URL/请求参数/响应结构，按抖音 fetch_orders_via_xhr 模式实现：
    # 用 page.request 或 page.goto 触发 XHR，解析响应 rows，映射成 ingest body 的 order 字段。
    raise NotImplementedError(
        "PDD_ORDERS_NEED_DAY0: 拼多多订单接口尚未完成 Day0 探测。"
        "请用真实账号登录 mms.pinduoduo.com 后，在订单管理页抓取列表 XHR 并填入 pdd_tasks.py。"
    )


def fetch_products_via_xhr(page) -> tuple[list[dict[str, Any]], str]:
    """抓取商品列表。返回 (rows, source_url)。

    本地开发：返回 Mock 数据
    生产：需完成 Day0 probe 后实现真实 XHR 调用
    """
    if _MOCK_PRODUCTS_ENABLED:
        from app.mock_pdd import mock_products_sync_data
        store_id = None
        return mock_products_sync_data(0, store_id)

    # TODO(probe): 账号到位后，在商品管理页抓取列表 XHR 并实现。
    raise NotImplementedError(
        "PDD_PRODUCTS_NEED_DAY0: 拼多多商品接口尚未完成 Day0 探测。"
        "请用真实账号登录 mms.pinduoduo.com 后，在商品管理页抓取列表 XHR 并填入 pdd_tasks.py。"
    )


def fetch_compass_via_xhr(page, *, date_type: int = 1) -> tuple[dict[str, Any], str]:
    """抓取经营罗盘。返回 (payload, source_url)。

    本地开发：返回 Mock 数据
    生产：需完成 Day0 probe 后实现真实 XHR 调用
    """
    if _MOCK_COMPASS_ENABLED:
        from app.mock_pdd import mock_compass_sync_data
        store_id = None
        return mock_compass_sync_data(0, date_type, store_id)

    # TODO(probe): 账号到位后，在数据中心/罗盘页抓取核心指标 XHR 并实现。
    raise NotImplementedError(
        "PDD_COMPASS_NEED_DAY0: 拼多多经营罗盘接口尚未完成 Day0 探测。"
        "请用真实账号登录 mms.pinduoduo.com 后，在数据中心抓取罗盘 XHR 并填入 pdd_tasks.py。"
    )


# ============================================================================
# 同步任务（对齐抖音 run_*_sync，回写 Java ingest）
# ============================================================================

def _resolve_store_id(client, tenant_id: int, store_id: str) -> str:
    store_id = (store_id or "").strip()
    if store_id:
        return store_id
    try:
        accounts = client.list_platform_accounts(tenant_id) or {}
    except Exception:
        accounts = {}
    pdd = accounts.get("pdd") or accounts.get("items") or []
    if isinstance(pdd, list) and pdd:
        return str(pdd[0].get("id") or "").strip()
    return ""


def _today_str() -> str:
    return datetime.now(SHANGHAI).strftime("%Y-%m-%d")


def run_orders_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    job_id = str(payload.get("job_id") or "")
    date_window = str(payload.get("date_window") or "today").strip() or "today"

    # Mock 模式下跳过 XHR_READY 检查
    if not _MOCK_ORDERS_ENABLED and not PDD_ORDERS_XHR_READY:
        raise RuntimeError(
            "PDD_ORDERS_NEED_DAY0: 拼多多订单接口尚未完成 Day0 探测固化"
        )

    store_id = _resolve_store_id(client, tenant_id, str(payload.get("store_id") or ""))
    if not store_id:
        store_id = "default"

    pw = context = page = None
    try:
        pw, context, page = _launch(
            tenant_id, headless=True, force_navigate=True, store_id=store_id,
        )
        if not _MOCK_ORDERS_ENABLED:
            # 非 Mock 模式需要真实登录检查
            if not _looks_logged_in(page, context):
                print(f"[PddOrders] not logged in; keep window open {_cookie_summary(context)}", flush=True)
                logged_in, page = _wait_until_logged_in(
                    page, context, timeout_seconds=300, label="orders_sync",
                )
                if not logged_in:
                    raise RuntimeError("PDD_NOT_LOGGED_IN: 拼多多商家后台未登录，请打开登录窗口完成登录")
        orders, source_url = fetch_orders_via_xhr(page, date_window=date_window)
    finally:
        _close_pw(pw, context)

    replace_day = _today_str()
    ingest_body = {
        "job_id": job_id,
        "store_id": store_id,
        "date_window": date_window,
        "source_url": source_url,
        "replace_day": replace_day,
        "orders": orders,
    }
    client.ingest_pdd_orders(ingest_body)
    return {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "scope": "orders",
        "orders_count": len(orders),
        "partial": False,
        "message": f"已同步订单（{date_window}）{len(orders)} 条",
        "synced_at": datetime.now(SHANGHAI).isoformat(),
        "source_url": source_url,
    }


def run_products_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    job_id = str(payload.get("job_id") or "")

    # Mock 模式下跳过 XHR_READY 检查
    if not _MOCK_PRODUCTS_ENABLED and not PDD_PRODUCTS_XHR_READY:
        raise RuntimeError(
            "PDD_PRODUCTS_NEED_DAY0: 拼多多商品接口尚未完成 Day0 探测固化"
        )

    store_id = _resolve_store_id(client, tenant_id, str(payload.get("store_id") or ""))
    if not store_id:
        store_id = "default"

    pw = context = page = None
    try:
        pw, context, page = _launch(
            tenant_id, headless=True, force_navigate=True, store_id=store_id,
        )
        if not _MOCK_PRODUCTS_ENABLED:
            # 非 Mock 模式需要真实登录检查
            if not _looks_logged_in(page, context):
                logged_in, page = _wait_until_logged_in(
                    page, context, timeout_seconds=300, label="products_sync",
                )
                if not logged_in:
                    raise RuntimeError("PDD_NOT_LOGGED_IN: 拼多多商家后台未登录，请打开登录窗口完成登录")
        products, source_url = fetch_products_via_xhr(page)
    finally:
        _close_pw(pw, context)

    ingest_body = {
        "job_id": job_id,
        "store_id": store_id,
        "source_url": source_url,
        "products": products,
    }
    client.ingest_pdd_products(ingest_body)
    return {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "scope": "products",
        "products_count": len(products),
        "partial": False,
        "message": f"已同步商品 {len(products)} 条",
        "synced_at": datetime.now(SHANGHAI).isoformat(),
        "source_url": source_url,
    }


def run_compass_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    job_id = str(payload.get("job_id") or "")
    date_type = int(payload.get("date_type") or 1)

    # Mock 模式下跳过 XHR_READY 检查
    if not _MOCK_COMPASS_ENABLED and not PDD_COMPASS_XHR_READY:
        raise RuntimeError(
            "PDD_COMPASS_NEED_DAY0: 拼多多经营罗盘接口尚未完成 Day0 探测固化"
        )

    store_id = _resolve_store_id(client, tenant_id, str(payload.get("store_id") or ""))
    if not store_id:
        store_id = "default"

    pw = context = page = None
    try:
        pw, context, page = _launch(
            tenant_id, headless=True, force_navigate=True, store_id=store_id,
        )
        if not _MOCK_COMPASS_ENABLED:
            # 非 Mock 模式需要真实登录检查
            if not _looks_logged_in(page, context):
                logged_in, page = _wait_until_logged_in(
                    page, context, timeout_seconds=300, label="compass_sync",
                )
                if not logged_in:
                    raise RuntimeError("PDD_NOT_LOGGED_IN: 拼多多商家后台未登录，请打开登录窗口完成登录")
        payload_data, source_url = fetch_compass_via_xhr(page, date_type=date_type)
    finally:
        _close_pw(pw, context)

    window = next(
        (w["window"] for w in PDD_COMPASS_DATE_TYPES if w["date_type"] == date_type),
        "realtime",
    )
    ingest_body = {
        "job_id": job_id,
        "store_id": store_id,
        "date_type": date_type,
        "date_window": window,
        "payload": payload_data,
        "raw_json": "",
    }
    client.ingest_pdd_compass(ingest_body)
    return {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "scope": "compass",
        "compass_count": 1,
        "partial": False,
        "message": f"已同步罗盘（{window}）",
        "synced_at": datetime.now(SHANGHAI).isoformat(),
        "source_url": source_url,
    }
