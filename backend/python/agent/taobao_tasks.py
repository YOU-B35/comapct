"""Taobao (淘宝) Agent tasks: login / probe / orders / products / compass sync.

复刻 ``pdd_tasks`` 接入模式：Playwright 持久化 Profile + 卖家后台 XHR。
数据 scope：订单（按 date_window 时间段分）/ 商品 / 生意参谋。

<b>当前为 probe-就绪骨架</b>：登录/会话探测/浏览器生命周期已可用，
但 ``TAOBAO_ORDERS_XHR_READY`` / ``TAOBAO_PRODUCTS_XHR_READY`` / ``TAOBAO_COMPASS_XHR_READY``
默认 ``False``——需用真实账号在 myseller.taobao.com 完成 Day0 probe，
抓出订单/商品/生意参谋三类 XHR 的 URL/参数/响应结构，固化到下面对应常量与
``fetch_*_via_xhr`` 实现后，三端数据流即可跑通。
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.browser.taobao_context import (
    TAOBAO_SELLER_HOME,
    close_taobao_profile_browsers,
    ensure_taobao_home_page,
    install_taobao_only_tab_guard,
    launch_taobao_persistent_context,
    sanitize_profile_startup_for_taobao,
)
from app.session_scope import normalize_session_key, resolve_platform_profile_dir

# ============================================================================
# Day0 probe 冻结标记（账号到位 probe 后改 True 并填下方 XHR 常量）
# ============================================================================
TAOBAO_ORDERS_XHR_READY = False
TAOBAO_PRODUCTS_XHR_READY = False
TAOBAO_COMPASS_XHR_READY = False

# TODO(probe): 淘宝卖家后台订单列表 XHR（myseller.taobao.com / trade.taobao.com 下，待 probe 填入）
TAOBAO_ORDER_LIST_PAGE = "https://myseller.taobao.com/home.htm"  # 占位，待 probe 校正
TAOBAO_ORDER_LIST_API = ""  # TODO(probe): 订单列表 XHR URL

# TODO(probe): 商品列表 XHR（卖家中心商品管理）
TAOBAO_PRODUCT_LIST_PAGE = "https://myseller.taobao.com/home.htm"  # 占位
TAOBAO_PRODUCT_LIST_API = ""  # TODO(probe)

# TODO(probe): 生意参谋 XHR（sycm.taobao.com 数据中心）
TAOBAO_COMPASS_PAGE = "https://sycm.taobao.com/"  # 占位
TAOBAO_COMPASS_CORE_API = ""  # TODO(probe)
TAOBAO_COMPASS_DATE_TYPES: list[dict[str, Any]] = [
    {"date_type": 1, "label": "实时", "window": "realtime"},
    {"date_type": 20, "label": "近1天", "window": "d1"},
    {"date_type": 21, "label": "近7天", "window": "d7"},
    {"date_type": 23, "label": "近30天", "window": "d30"},
]

# 淘宝登录态 cookie 标记（probe 后可补充；先用常见 token）
_AUTH_COOKIE_MARKERS = (
    "cookie17",
    "_tb_token_",
    "unb",
    "cookie2",
    "sgcookie",
    "_m_h5_tk",
    "login5ssn",
    "cna",
    "isg",
    "t",
)

_LOGIN_CTA_MARKERS = (
    "扫码登录",
    "账号登录",
    "手机号登录",
    "验证码登录",
    "登录淘宝",
    "登录天猫",
    "请登录",
    "立即登录",
    "密码登录",
)

ROOT = Path(__file__).resolve().parents[1]
SHANGHAI = ZoneInfo("Asia/Shanghai")


def profile_dir(tenant_id: int, store_id: str | None = None) -> Path:
    key = normalize_session_key(store_id)
    if key == "default":
        legacy = ROOT / ".taobao-browser-profile" / f"tenant-{int(tenant_id)}"
        legacy.mkdir(parents=True, exist_ok=True)
        return legacy
    path = resolve_platform_profile_dir(
        "taobao",
        tenant_id,
        key,
        root=ROOT / ".taobao-browser-profile",
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_in_clean_thread(fn, *, timeout: float | None = None):
    """Playwright Sync API cannot run when the current thread already has an asyncio loop."""
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        return fut.result(timeout=timeout)


def _taobao_launch_kwargs(*, headless: bool) -> dict[str, Any]:
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
            f"--homepage={TAOBAO_SELLER_HOME}",
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


def _has_taobao_profile_lock(profile_dir: Path) -> bool:
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
    if _has_taobao_profile_lock(user_dir):
        print("[TaobaoBrowser] stale profile lock present, reclaiming before launch…", flush=True)
        close_taobao_profile_browsers(user_dir)
    sanitize_profile_startup_for_taobao(user_dir, home_url=TAOBAO_SELLER_HOME)
    launch_kwargs = _taobao_launch_kwargs(headless=headless)
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
        context = launch_taobao_persistent_context(
            playwright=None,
            profile_dir=user_dir,
            launch_kwargs=launch_kwargs,
            launch_fn=launch_fn,
            reclaim_fn=lambda: close_taobao_profile_browsers(user_dir),
        )
    except Exception:
        _close_pw(state["pw"], None)
        raise
    install_taobao_only_tab_guard(context)
    page = ensure_taobao_home_page(context, force_navigate=force_navigate)
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
        if not any(host in domain for host in ("taobao", "tmall", "alicdn")):
            continue
        if any(marker in name for marker in _AUTH_COOKIE_MARKERS):
            return True
    return False


def _looks_logged_in(page, context=None) -> bool:
    """Require real auth cookies + console chrome; reject login CTA pages."""
    url = (page.url or "").lower()
    if "login" in url or "passport" in url or "sso" in url:
        return False
    if "taobao.com" not in url and "tmall.com" not in url:
        return False
    try:
        body = page.inner_text("body", timeout=3000)
    except Exception:
        body = ""
    if any(marker in body for marker in _LOGIN_CTA_MARKERS):
        return False
    markers = ("订单", "商品", "售后", "数据", "首页", "千牛", "淘宝卖家", "生意参谋")
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
            from app.browser.taobao_context import close_foreign_taobao_pages

            close_foreign_taobao_pages(context)
        except Exception:
            pass
        logged_in = _looks_logged_in(current, context)
        now_ts = time.time()
        if logged_in:
            return True, current
        if now_ts - last_log > 5:
            print(
                f"[TaobaoLogin:{label}] waiting login… url={current.url!r} "
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
                f"[TaobaoProbe] tenant={tenant_id} logged_in={logged_in} "
                f"url={page.url!r} {_cookie_summary(context)}",
                flush=True,
            )
            return {
                "tenant_id": tenant_id,
                "ready": logged_in,
                "logged_in": logged_in,
                "requires_auth": not logged_in,
                "profile_busy": False,
                "message": "淘宝已登录" if logged_in else "淘宝未登录，请打开登录窗口完成登录",
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
            print(f"[TaobaoLogin] opened {TAOBAO_SELLER_HOME} tenant={tenant_id}", flush=True)
            logged_in, page = _wait_until_logged_in(
                page, context, timeout_seconds=timeout_seconds, label="open_login",
            )
            return {
                "tenant_id": tenant_id,
                "ready": logged_in,
                "logged_in": logged_in,
                "requires_auth": not logged_in,
                "profile_busy": False,
                "message": "淘宝已登录" if logged_in else "登录超时，请重试打开登录窗口",
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

    TODO(probe): 账号到位后，在 myseller.taobao.com / trade.taobao.com 订单页
    打开 DevTools Network，抓出订单列表 XHR 的 URL/请求参数/响应结构，
    按 pdd_tasks.fetch_orders_via_xhr 模式实现：用 page.request 或 page.goto 触发 XHR，
    解析响应 rows，映射成 ingest body 的 order 字段。
    """
    raise NotImplementedError(
        "TAOBAO_ORDERS_NEED_DAY0: 淘宝订单接口尚未完成 Day0 探测。"
        "请用真实账号登录 myseller.taobao.com 后，在订单管理页抓取列表 XHR 并填入 taobao_tasks.py。"
    )


def fetch_products_via_xhr(page) -> tuple[list[dict[str, Any]], str]:
    """抓取商品列表。返回 (rows, source_url)。

    TODO(probe): 账号到位后，在卖家中心商品管理页抓取列表 XHR 并实现。
    """
    raise NotImplementedError(
        "TAOBAO_PRODUCTS_NEED_DAY0: 淘宝商品接口尚未完成 Day0 探测。"
        "请用真实账号登录 myseller.taobao.com 后，在商品管理页抓取列表 XHR 并填入 taobao_tasks.py。"
    )


def fetch_compass_via_xhr(page, *, date_type: int = 1) -> tuple[dict[str, Any], str]:
    """抓取生意参谋。返回 (payload, source_url)。

    TODO(probe): 账号到位后，在 sycm.taobao.com 数据中心抓取核心指标 XHR 并实现。
    """
    raise NotImplementedError(
        "TAOBAO_COMPASS_NEED_DAY0: 淘宝生意参谋接口尚未完成 Day0 探测。"
        "请用真实账号登录 sycm.taobao.com 后，在数据中心抓取 XHR 并填入 taobao_tasks.py。"
    )


# ============================================================================
# 同步任务（对齐 pdd run_*_sync，回写 Java ingest）
# ============================================================================

def _resolve_store_id(client, tenant_id: int, store_id: str) -> str:
    store_id = (store_id or "").strip()
    if store_id:
        return store_id
    try:
        accounts = client.list_platform_accounts(tenant_id) or {}
    except Exception:
        accounts = {}
    taobao = accounts.get("taobao") or accounts.get("items") or []
    if isinstance(taobao, list) and taobao:
        return str(taobao[0].get("id") or "").strip()
    return ""


def _today_str() -> str:
    return datetime.now(SHANGHAI).strftime("%Y-%m-%d")


def run_orders_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    job_id = str(payload.get("job_id") or "")
    date_window = str(payload.get("date_window") or "today").strip() or "today"

    if not TAOBAO_ORDERS_XHR_READY:
        raise RuntimeError(
            "TAOBAO_ORDERS_NEED_DAY0: 淘宝订单接口尚未完成 Day0 探测固化"
        )

    store_id = _resolve_store_id(client, tenant_id, str(payload.get("store_id") or ""))
    if not store_id:
        store_id = "default"

    pw = context = page = None
    try:
        pw, context, page = _launch(
            tenant_id, headless=False, force_navigate=True, store_id=store_id,
        )
        if not _looks_logged_in(page, context):
            print(f"[TaobaoOrders] not logged in; keep window open {_cookie_summary(context)}", flush=True)
            logged_in, page = _wait_until_logged_in(
                page, context, timeout_seconds=300, label="orders_sync",
            )
            if not logged_in:
                raise RuntimeError("TAOBAO_NOT_LOGGED_IN: 淘宝卖家后台未登录，请打开登录窗口完成登录")
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
    client.ingest_taobao_orders(ingest_body)
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

    if not TAOBAO_PRODUCTS_XHR_READY:
        raise RuntimeError(
            "TAOBAO_PRODUCTS_NEED_DAY0: 淘宝商品接口尚未完成 Day0 探测固化"
        )

    store_id = _resolve_store_id(client, tenant_id, str(payload.get("store_id") or ""))
    if not store_id:
        store_id = "default"

    pw = context = page = None
    try:
        pw, context, page = _launch(
            tenant_id, headless=False, force_navigate=True, store_id=store_id,
        )
        if not _looks_logged_in(page, context):
            logged_in, page = _wait_until_logged_in(
                page, context, timeout_seconds=300, label="products_sync",
            )
            if not logged_in:
                raise RuntimeError("TAOBAO_NOT_LOGGED_IN: 淘宝卖家后台未登录，请打开登录窗口完成登录")
        products, source_url = fetch_products_via_xhr(page)
    finally:
        _close_pw(pw, context)

    ingest_body = {
        "job_id": job_id,
        "store_id": store_id,
        "source_url": source_url,
        "products": products,
    }
    client.ingest_taobao_products(ingest_body)
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

    if not TAOBAO_COMPASS_XHR_READY:
        raise RuntimeError(
            "TAOBAO_COMPASS_NEED_DAY0: 淘宝生意参谋接口尚未完成 Day0 探测固化"
        )

    store_id = _resolve_store_id(client, tenant_id, str(payload.get("store_id") or ""))
    if not store_id:
        store_id = "default"

    pw = context = page = None
    try:
        pw, context, page = _launch(
            tenant_id, headless=False, force_navigate=True, store_id=store_id,
        )
        if not _looks_logged_in(page, context):
            logged_in, page = _wait_until_logged_in(
                page, context, timeout_seconds=300, label="compass_sync",
            )
            if not logged_in:
                raise RuntimeError("TAOBAO_NOT_LOGGED_IN: 淘宝卖家后台未登录，请打开登录窗口完成登录")
        payload_data, source_url = fetch_compass_via_xhr(page, date_type=date_type)
    finally:
        _close_pw(pw, context)

    window = next(
        (w["window"] for w in TAOBAO_COMPASS_DATE_TYPES if w["date_type"] == date_type),
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
    client.ingest_taobao_compass(ingest_body)
    return {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "scope": "compass",
        "compass_count": 1,
        "partial": False,
        "message": f"已同步生意参谋（{window}）",
        "synced_at": datetime.now(SHANGHAI).isoformat(),
        "source_url": source_url,
    }
