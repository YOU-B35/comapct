"""Pinduoduo (拼多多) Agent tasks: login / probe / orders / products / compass sync.

复刻 ``douyin_tasks`` 接入模式：Playwright 持久化 Profile + 卖家后台 XHR。
数据 scope：订单（按 date_window 时间段分）/ 商品 / 经营罗盘 / 售后问题。

<b>数据直连模式</b>：登录/会话探测/浏览器生命周期可用，
``fetch_*_via_xhr`` 打开对应后台页面后运行时自动发现列表 XHR
（无需手工 Day0 probe），按页重放拉取全量数据并映射为 ingest 字段。
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.browser.pdd_context import (
    PDD_SELLER_HOME,
    close_pdd_profile_browsers,
    ensure_pdd_home_page,
    install_pdd_only_tab_guard,
    is_pdd_web_url,
    launch_pdd_persistent_context,
    pdd_home_url,
    sanitize_profile_startup_for_pdd,
)
from app.timezone import SHANGHAI
from app.browser.resource_filter import install_heavy_resource_filter
from app.observability.task_timing import timed_stage
from app.session_scope import normalize_session_key, resolve_platform_profile_dir
from app.rate_limit import TokenBucket
# ============================================================================
# PDD 数据源：真实接口直连（运行时自动发现 mms.pinduoduo.com 列表 XHR 并分页拉全量）
# ============================================================================
# 已启用真实 XHR 抓取：不再使用本地 Mock 数据，所有同步数据均从拼多多商家后台接口获取。
PDD_ORDERS_XHR_READY = True
PDD_PRODUCTS_XHR_READY = True
PDD_COMPASS_XHR_READY = True
PDD_ISSUES_XHR_READY = True

_MOCK_ORDERS_ENABLED = False
_MOCK_PRODUCTS_ENABLED = False
_MOCK_COMPASS_ENABLED = False
_MOCK_ISSUES_ENABLED = False

# 页面候选（多个地址兼容后台改版；抓取时逐个尝试）
PDD_ORDER_LIST_PAGE = "https://mms.pinduoduo.com/orders/list"
PDD_ORDER_LIST_PAGE_CANDIDATES = (
    "https://mms.pinduoduo.com/orders/list",
    "https://mms.pinduoduo.com/od/index.html",
    "https://mms.pinduoduo.com/order/index.html",
)
PDD_ORDER_LIST_API = "https://mms.pinduoduo.com/mangkhut/mms/recentOrderList"  # 已冻结，直连优先
PDD_ORDER_LIST_API_CANDIDATES = (
    "https://mms.pinduoduo.com/mangkhut/mms/recentOrderList",
    "https://mms.pinduoduo.com/mangkhut/mms/order/queryOrderList",
)

PDD_PRODUCT_LIST_PAGE = "https://mms.pinduoduo.com/goods/goods_list"
PDD_PRODUCT_LIST_PAGE_CANDIDATES = (
    "https://mms.pinduoduo.com/goods/goods_list",
    "https://mms.pinduoduo.com/goods/goodsList",
    "https://mms.pinduoduo.com/goods/goods_list.html",
)
PDD_PRODUCT_LIST_API = "https://mms.pinduoduo.com/vodka/v2/mms/query/display/mall/goodsList"  # 已冻结，直连优先
PDD_PRODUCT_LIST_API_CANDIDATES = (
    "https://mms.pinduoduo.com/vodka/v2/mms/query/display/mall/goodsList",
    "https://mms.pinduoduo.com/mangkhut/mms/goods/goodsList",
    "https://mms.pinduoduo.com/goods/goodsList",
)

PDD_COMPASS_PAGE = "https://mms.pinduoduo.com/sycm/stores_data"
PDD_COMPASS_PAGE_CANDIDATES = (
    "https://mms.pinduoduo.com/sycm/stores_data",
    "https://mms.pinduoduo.com/sycm/data/overview",
)
PDD_COMPASS_CORE_API = ""
PDD_ISSUE_LIST_PAGE = "https://mms.pinduoduo.com/aftersales/aftersale_list"
PDD_ISSUE_LIST_PAGE_CANDIDATES = (
    "https://mms.pinduoduo.com/aftersales/aftersale_list",
    "https://mms.pinduoduo.com/aftersales/work_order/list",
    "https://mms.pinduoduo.com/aftersale/index.html",
)
PDD_ISSUE_LIST_API = ""

# 直连重放时的完整浏览器请求头（伪装用）：不能只带 Content-Type/UA。
# 缺省值补齐浏览器真实调用特征；captured headers 中的签名/鉴权字段优先生效。
_PDD_BROWSER_HEADERS: dict[str, str] = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://mms.pinduoduo.com",
    "referer": "https://mms.pinduoduo.com/orders/list",
    "sec-ch-ua": '"Chromium";v="130", "Not?A_Brand";v="99", "Microsoft Edge";v="130"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "x-requested-with": "XMLHttpRequest",
}

_PDD_REFERERS: dict[str, str] = {
    "orders": "https://mms.pinduoduo.com/orders/list",
    "products": "https://mms.pinduoduo.com/goods/goods_list",
    "issues": "https://mms.pinduoduo.com/aftersales/aftersale_list",
}


def _pdd_replay_headers(kind: str, captured: dict[str, Any] | None = None) -> dict[str, str]:
    """合并缺省完整请求头与已捕获请求头（captured 的签名/鉴权字段优先生效）。"""
    merged = dict(_PDD_BROWSER_HEADERS)
    merged["referer"] = _PDD_REFERERS.get(kind, merged["referer"])
    if isinstance(captured, dict):
        for k, v in (captured.get("headers") or {}).items():
            if isinstance(v, str) and k.lower() not in {"content-length", "host", "connection", "cookie"}:
                merged[k] = v
    return merged


def _pdd_page_sleep(kind: str) -> float:
    """页间隔：订单 1.2s / 商品 1.0s + 0.3s 抖动（env 可调），避免请求过密触发频控。"""
    default = "1.2" if kind == "orders" else "1.0"
    base = float(os.getenv("PDD_PAGE_SLEEP_SECONDS", default) or default)
    jitter = float(os.getenv("PDD_PAGE_SLEEP_JITTER", "0.25") or "0.25")
    return max(0.4, base + random.uniform(0, jitter))


PDD_COMPASS_DATE_TYPES: list[dict[str, Any]] = [
    {"date_type": 1, "label": "实时", "window": "realtime"},
    {"date_type": 20, "label": "近1天", "window": "d1"},
    {"date_type": 21, "label": "近7天", "window": "d7"},
    {"date_type": 23, "label": "近30天", "window": "d30"},
]

# 冻结接口缓存：首次发现列表 XHR 后写盘，后续同步直接按缓存 URL 发请求，
# 不再每次打开页面监听网络（接口拿到一次后固化复用）。
_PDD_XHR_CACHE_NAME = ".pdd-xhr-cache.json"

# 按天节奏令牌桶：默认等价于原 3s/天，但按令牌匀速发放并支持突发。
_PDD_DAY_BUCKET = TokenBucket(
    rate=1.0 / max(float(os.getenv("PDD_DAY_PACING_SECONDS", "1.0") or "1.0"), 0.5),
    capacity=1.0,
)

# 拼多多登录态 cookie 标记：卖家后台与买家端共用。买家端常见
# PDDAccessToken / api_uid / pdd_user_id；匹配时忽略大小写。
_AUTH_COOKIE_MARKERS = (
    "PASS_ID",
    "ruipk",
    "ruidp",
    "rpcc_id",
    "pdd_user_id",
    "pdd_user_uid",
    "pdd_cookie",
    "J-sessionid",
    "PDDAccessToken",
    "api_uid",
    "access_token",
    "pdd_token",
    "pddpassport",
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

# 买家端（mobile.yangkeduo.com）登录后首页/个人页的导航文案；与卖家后台 markers 分开判定。
_BUYER_LOGGED_IN_MARKERS = (
    "首页",
    "分类",
    "购物车",
    "我的",
    "订单",
    "搜索",
    "拼多多",
)

ROOT = Path(__file__).resolve().parents[1]


def _env_int(name: str, default: int, minimum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _env_float(name: str, default: float, minimum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


PDD_XHR_NAV_TIMEOUT_MS = _env_int("PDD_XHR_NAV_TIMEOUT_MS", 45_000, 15_000)
PDD_XHR_CAPTURE_TIMEOUT_SECONDS = _env_float("PDD_XHR_CAPTURE_TIMEOUT_SECONDS", 30.0, 8.0)
PDD_XHR_DIRECT_TIMEOUT_MS = _env_int("PDD_XHR_DIRECT_TIMEOUT_MS", 30_000, 10_000)
PDD_XHR_REPLAY_TIMEOUT_MS = _env_int("PDD_XHR_REPLAY_TIMEOUT_MS", 35_000, 10_000)
PDD_SELLER_HOME_TIMEOUT_MS = _env_int("PDD_SELLER_HOME_TIMEOUT_MS", 45_000, 15_000)


def _pdd_config_paths() -> list[Path]:
    paths: list[Path] = []
    if getattr(sys, "frozen", False):
        paths.append(Path(sys.executable).resolve().parent / "config.json")
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        paths.append(Path(local) / "CrossHub" / "SyncHelper" / "config.json")
    return paths


def _pdd_profile_root() -> Path:
    """解析拼多多浏览器 profile 根目录。

    优先顺序：PDD_PROFILE_ROOT 环境变量 -> 助手 config.json 的 pdd_profile_root
    -> 冻结版按 <项目根>/backend/python 定位（保持与开发模式一致，避免每次
    重新打包都把已登录的 profile 丢进 _internal）-> 代码目录（开发模式）。
    """
    env = (os.environ.get("PDD_PROFILE_ROOT") or "").strip()
    if env:
        return Path(env)
    for cfg_path in _pdd_config_paths():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        value = (cfg.get("pdd_profile_root") or "").strip()
        if value:
            return Path(os.path.expandvars(value))
    if getattr(sys, "frozen", False):
        # EXE 位于 <项目>/dist/CrossHub-Sync-Helper/CrossHub-Sync-Helper/ 下
        candidate = Path(sys.executable).resolve().parents[3] / "backend" / "python"
        if candidate.exists():
            return candidate
    return ROOT


def profile_dir(tenant_id: int, store_id: str | None = None) -> Path:
    """按店铺隔离持久化浏览器 profile（对齐 1688 多账号设计）。

    未指定店铺（default/全部）沿用 ``tenant-{id}`` 平铺目录（默认账号）；
    指定店铺使用 ``tenant-{id}/account-{store_id}``，各店登录态独立。
    """
    key = normalize_session_key(store_id)
    root = _pdd_profile_root()
    if key == "default":
        path = root / ".pdd-browser-profile" / f"tenant-{int(tenant_id)}"
    else:
        path = resolve_platform_profile_dir(
            "pdd",
            tenant_id,
            key,
            root=root / ".pdd-browser-profile",
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
    from app.browser.context import _bundled_chromium_ready

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
    # 统一使用 Playwright 内置 Chromium（无头/有头均不打开系统 Chrome/Edge），
    # 避免系统浏览器指纹触发平台风控。
    if not _bundled_chromium_ready():
        raise RuntimeError(
            "PDD_BROWSER_UNAVAILABLE: 未检测到 Playwright 内置 Chromium。"
            "拼多多登录/同步统一使用内置浏览器（不打开系统 Chrome/Edge），"
            "请先执行 python -m playwright install chromium 后重试"
        )
    return kwargs


def _has_pdd_profile_lock(profile_dir: Path) -> bool:
    root = Path(profile_dir)
    if (root / "SingletonLock").exists() or (root / "lockfile").exists():
        return True
    return (root / "Default" / "LOCK").exists()


def _close_pw(pw, context) -> None:
    """Graceful close so cookies flush before next sync."""
    tmp_profile = None
    try:
        if context is not None:
            tmp_profile = getattr(context, "_pdd_sync_profile_tmp", None)
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
    if tmp_profile is not None:
        try:
            shutil.rmtree(tmp_profile, ignore_errors=True)
        except Exception:  # noqa: BLE001
            pass


def _clone_pdd_profile(master: Path) -> Path | None:
    """Copy the logged-in profile so headless sync cannot clobber the master cookies.

    同步用无头浏览器跑在副本上：即使平台让无头会话失效/写回登出 cookie，
    主 profile 的登录态也保持不变，下次 probe 仍显示已登录。
    """
    try:
        if not master.is_dir():
            return None
        tmp = master.parent / f"{master.name}.sync-{int(time.time() * 1000)}"
        shutil.copytree(
            master,
            tmp,
            ignore=shutil.ignore_patterns(
                "SingletonLock",
                "SingletonSocket",
                "SingletonCookie",
                "DevToolsActivePort",
                "lockfile",
                "LOCK",
                "*.tmp",
            ),
        )
        return tmp
    except Exception as exc:  # noqa: BLE001
        print(f"[PddBrowser] profile clone failed, fallback to master: {exc}", flush=True)
        return None


def _launch(
    tenant_id: int,
    *,
    headless: bool = False,
    force_navigate: bool = True,
    store_id: str | None = None,
    profile_dir_override: Path | None = None,
    home_url: str | None = None,
):
    from playwright.sync_api import sync_playwright

    user_dir = profile_dir_override if profile_dir_override is not None else profile_dir(tenant_id, store_id)
    if _has_pdd_profile_lock(user_dir):
        print("[PddBrowser] stale profile lock present, reclaiming before launch…", flush=True)
        close_pdd_profile_browsers(user_dir)
    home_url = home_url or pdd_home_url(store_id)
    sanitize_profile_startup_for_pdd(user_dir, home_url=home_url)
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
        with timed_stage("browser_launch.pdd"):
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
    install_heavy_resource_filter(context, headless=headless)
    install_pdd_only_tab_guard(context)
    page = ensure_pdd_home_page(context, force_navigate=force_navigate, home_url=home_url)
    return state["pw"], context, page


def _cookie_summary(context) -> str:
    try:
        cookies = context.cookies()
    except Exception:
        return "cookies=unreadable"
    names = sorted({str(c.get("name") or "") for c in cookies if c.get("name")})
    auth_hits = [
        n for n in names
        if any(m.upper() in n.upper() for m in _AUTH_COOKIE_MARKERS)
    ]
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
        name_upper = name.upper()
        if any(marker.upper() in name_upper for marker in _AUTH_COOKIE_MARKERS):
            return True
        if any(keyword in name_upper for keyword in ("UID", "TOKEN", "PASS", "SESSION", "LOGIN", "USER")):
            return True
    return False


def _looks_logged_in(page, context=None, *, buyer: bool = False) -> bool:
    """认证 cookie 是登录态强信号；卖家端无 cookie 时用页面文案兜底判定。"""
    if not is_pdd_web_url(page.url or ""):
        return False
    has_auth = context is not None and _has_auth_cookies(context)
    if buyer:
        # 买家首页的导航文案（首页/分类/购物车/我的）未登录也可见，
        # 因此买家态必须依据认证 cookie 判定，避免公开页误报。
        return has_auth
    try:
        body = page.inner_text("body", timeout=3000)
    except Exception:
        body = ""
    if has_auth:
        # 登录完成后页面可能仍停留在 login/next 地址或残留登录 CTA，
        # 此时 cookie 已说明登录完成，直接判定已登录。
        return True
    if any(marker in body for marker in _LOGIN_CTA_MARKERS):
        return False
    url = (page.url or "").lower()
    if "login" in url or "passport" in url or "sso" in url:
        return False
    markers = _BUYER_LOGGED_IN_MARKERS if buyer else ("订单", "商品", "售后", "数据", "首页", "拼多多商家")
    hits = sum(1 for m in markers if m in body)
    if hits < 2:
        return False
    return True


def _wait_until_logged_in(
    page,
    context,
    *,
    timeout_seconds: int,
    label: str,
    buyer: bool = False,
    home_url: str | None = None,
):
    deadline = time.time() + max(30, int(timeout_seconds))
    last_log = 0.0
    current = page
    while time.time() < deadline:
        try:
            from app.browser.pdd_context import close_foreign_pdd_pages

            close_foreign_pdd_pages(context)
        except Exception:
            pass
        try:
            current_url = (current.url or "").lower()
            if not is_pdd_web_url(current_url):
                # 已登录的会话访问首页会自动跳到商家后台；仅当停在空白/外部页时才回首页，
                # 避免把正在手动填写的登录表单强制跳走。
                current = ensure_pdd_home_page(
                    context,
                    force_navigate=True,
                    home_url=home_url or pdd_home_url("buyer" if buyer else None),
                )
        except Exception:
            pass
        logged_in = _looks_logged_in(current, context, buyer=buyer)
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
    return _looks_logged_in(current, context, buyer=buyer), current


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
            buyer = str(store_id or "").strip().lower() == "buyer"
            logged_in = _looks_logged_in(page, context, buyer=buyer)
            print(
                f"[PddProbe] tenant={tenant_id} logged_in={logged_in} "
                f"url={page.url!r} {_cookie_summary(context)}",
                flush=True,
            )
            if buyer:
                message = "拼多多买家态已登录" if logged_in else "拼多多买家态未登录，请打开登录窗口完成买家登录"
            else:
                message = "拼多多已登录" if logged_in else "拼多多未登录，请打开登录窗口完成登录"
            return {
                "tenant_id": tenant_id,
                "ready": logged_in,
                "logged_in": logged_in,
                "requires_auth": not logged_in,
                "profile_busy": False,
                "message": message,
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
            home_url = pdd_home_url(store_id)
            pw, context, page = _launch(
                tenant_id, headless=False, force_navigate=True, store_id=store_id,
            )
            print(f"[PddLogin] opened {home_url} tenant={tenant_id}", flush=True)
            logged_in, page = _wait_until_logged_in(
                page,
                context,
                timeout_seconds=timeout_seconds,
                label="open_login",
                buyer=str(store_id or "").strip().lower() == "buyer",
                home_url=home_url,
            )
            buyer = str(store_id or "").strip().lower() == "buyer"
            return {
                "tenant_id": tenant_id,
                "ready": logged_in,
                "logged_in": logged_in,
                "requires_auth": not logged_in,
                "profile_busy": False,
                "message": (
                    "拼多多买家态已登录" if logged_in and buyer
                    else "拼多多已登录" if logged_in
                    else "登录超时，请重试打开登录窗口"
                ),
                "shop_count": 0,
                "shops": [],
            }
        finally:
            _close_pw(pw, context)

    return _run_in_clean_thread(_run, timeout=float(timeout_seconds) + 90)


# ============================================================================
# XHR 抓取：真实接口直连（运行时自动发现 + 分页拉全量）
# ============================================================================

_XHR_IGNORE_TOKENS = (
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    "font",
    "image",
    "logo",
    "icon",
    "track",
    "logger",
    "metrics",
    "monitor",
    "collect",
    "upload",
    "sentry",
    "beacon",
    "recommend",
    "polyfill",
    "chunk",
    "vendor",
)

_ORDER_API_MARKERS = ("order", "/od/", "orderlist", "queryorder", "searchorder")
_ORDER_LIST_KEYWORDS = ("list", "query", "search", "page", "get")
_PRODUCT_API_MARKERS = ("goods", "product", "/gd/")
_PRODUCT_LIST_KEYWORDS = ("list", "query", "search", "page", "get", "manage")
_ISSUE_API_MARKERS = (
    "aftersale",
    "after-sale",
    "after_sale",
    "refund",
    "violation",
    "issue",
    "warning",
    "risk",
)
_ISSUE_LIST_KEYWORDS = ("list", "query", "search", "page", "get", "order")
_COMPASS_API_MARKERS = ("sydney", "malltrade", "mallcore", "mallscore", "mallinfo")
_COMPASS_LIST_KEYWORDS = ("trade", "info", "list", "config", "query", "get", "overview")

# PDD 商家后台金额单位是“分”，转成“元”展示（与抖音抓取口径一致）
_PDD_AMOUNT_IN_FEN = True


def _is_ignored_xhr_url(url: str) -> bool:
    u = (url or "").lower()
    return any(token in u for token in _XHR_IGNORE_TOKENS)


def _looks_kind_api_url(url: str, kind: str) -> bool:
    u = (url or "").lower()
    if "pinduoduo.com" not in u and "yangkeduo" not in u:
        return False
    if _is_ignored_xhr_url(u):
        return False
    if kind == "orders":
        # 合并发货列表（newOrderList）只含少量“待合并发货”单，不是完整订单列表，必须排除；
        # recentOrderList 才是订单页真正的列表接口（result.pageItems / totalItemNum）。
        if "mergeshipping" in u or "merge_shipping" in u:
            return False
        if "neworderlist" in u:
            return False
        if "recentorderlist" in u:
            return True
        markers, keywords = _ORDER_API_MARKERS, _ORDER_LIST_KEYWORDS
    elif kind == "products":
        markers, keywords = _PRODUCT_API_MARKERS, _PRODUCT_LIST_KEYWORDS
    elif kind == "issues":
        markers, keywords = _ISSUE_API_MARKERS, _ISSUE_LIST_KEYWORDS
    elif kind == "compass":
        markers, keywords = _COMPASS_API_MARKERS, _COMPASS_LIST_KEYWORDS
    else:
        return False
    return any(m in u for m in markers) and any(k in u for k in keywords)


def _json_get(data: Any, *path: str) -> Any:
    node = data
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _row_looks_like_order(row: dict[str, Any]) -> bool:
    order_id = (
        row.get("order_sn")
        or row.get("orderSn")
        or row.get("order_no")
        or row.get("orderNo")
        or row.get("order_id")
        or row.get("orderId")
    )
    if order_id in (None, ""):
        return False
    blob = json.dumps(row, ensure_ascii=False).lower()
    return any(
        token in blob
        for token in (
            "goods_list",
            "goodslist",
            "goods",
            "pay_amount",
            "payamount",
            "order_amount",
            "orderamount",
            "create_time",
            "createtime",
            "status",
            "sku",
            "mall",
            "receiver",
        )
    )


def _row_looks_like_product(row: dict[str, Any]) -> bool:
    product_id = (
        row.get("goods_id")
        or row.get("goodsId")
        or row.get("product_id")
        or row.get("productId")
        or row.get("goods_sn")
        or row.get("goodsSn")
        or row.get("id")
    )
    if product_id in (None, ""):
        return False
    blob = json.dumps(row, ensure_ascii=False).lower()
    has_name = any(
        token in blob
        for token in (
            "goods_name",
            "goodsname",
            "product_name",
            "productname",
            '"name"',
            "title",
            "goods_desc",
            "share_desc",
        )
    )
    has_money = any(token in blob for token in ("price", "amount", "market_price"))
    has_stock = any(
        token in blob
        for token in ("quantity", "stock", "sold_quantity", "sku_count", "reserve_quantity")
    )
    return has_name and (has_money or has_stock)


def _row_looks_like_issue(row: dict[str, Any]) -> bool:
    issue_id = (
        row.get("aftersale_id")
        or row.get("afterSaleId")
        or row.get("order_sn")
        or row.get("orderSn")
        or row.get("violation_id")
        or row.get("id")
    )
    if issue_id in (None, ""):
        return False
    blob = json.dumps(row, ensure_ascii=False).lower()
    return any(
        token in blob
        for token in (
            "after_sale",
            "aftersale",
            "refund",
            "violation",
            "warning",
            "risk",
            "type",
            "status",
            "reason",
        )
    )


def _find_list_rows(data: Any, kind: str) -> list[dict[str, Any]] | None:
    """Find the first plausible list of rows in a nested JSON response."""
    if not isinstance(data, dict):
        return None
    candidates: list[Any] = []

    def collect(node: Any) -> None:
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                candidates.append(value)
            elif isinstance(value, dict):
                collect(value)

    collect(data)
    for rows in candidates:
        rows = [r for r in rows if isinstance(r, dict)]
        if not rows:
            continue
        if kind == "orders" and _row_looks_like_order(rows[0]):
            return [r for r in rows if _row_looks_like_order(r)]
        if kind == "products" and _row_looks_like_product(rows[0]):
            return [r for r in rows if _row_looks_like_product(r)]
        if kind == "issues" and _row_looks_like_issue(rows[0]):
            return [r for r in rows if _row_looks_like_issue(r)]
    return None


def _extract_total_count(data: Any, page_rows: int) -> int:
    if not isinstance(data, dict):
        return page_rows
    # 先看顶层，再看常见包装节点（result / data）里的 total / totalItemNum。
    nodes: list[dict[str, Any]] = [data]
    for wrapper in ("result", "data"):
        wrapped = data.get(wrapper)
        if isinstance(wrapped, dict):
            nodes.append(wrapped)
    for node in nodes:
        for key in (
            "total",
            "total_count",
            "totalCount",
            "total_num",
            "totalNum",
            "total_item_num",
            "totalItemNum",
            "count",
        ):
            raw = node.get(key)
            if raw in (None, ""):
                continue
            try:
                value = int(raw)
            except Exception:
                continue
            if value >= page_rows:
                return value
    return page_rows


def _normalize_orders_post_data(post_data: str | None) -> str | None:
    """Force the recentOrderList payload to the '全部订单' query.

    The orders/list page first fires a small widget call (pageSize=1 +
    consolidateTypeList) and its main list defaults to the 待发货 tab
    (orderType=1/afterSaleType=1).  For full-store order sync we need the
    unfiltered list, so reset to orderType=0/afterSaleType=0 and drop the
    consolidateTypeList member, while keeping the captured group window and
    sort/mobile params.
    """
    if not post_data:
        return None
    try:
        payload = json.loads(post_data)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(payload, dict):
        return None
    out = dict(payload)
    out["orderType"] = 0
    out["afterSaleType"] = 0
    # 全部订单模式下 sortType=10 返回时间升序（最早 90 天前），
    # 改为 1 让服务端按时间倒序返回，第一页即最新订单。
    out["sortType"] = 1
    out.pop("consolidateTypeList", None)
    return json.dumps(out, ensure_ascii=False)

def _set_page_in_payload(payload: Any, page_no: int, page_size: int | None = None) -> Any:
    if isinstance(payload, dict):
        out = dict(payload)
        page_keys = (
            "page",
            "page_num",
            "pageNum",
            "pageNumber",
            "page_number",
            "page_no",
            "pageNo",
            "current",
            "current_page",
            "currentPage",
        )
        size_keys = ("pageSize", "page_size", "size", "limit", "count")
        touched = False
        for key in page_keys:
            if key in out:
                out[key] = page_no
                touched = True
        if page_size is not None:
            for key in size_keys:
                if key in out:
                    out[key] = page_size
                    touched = True
        if not touched:
            out["pageNum"] = page_no
            if page_size is not None:
                out["pageSize"] = page_size
        for nest_key in ("param", "params", "query", "request", "data"):
            if isinstance(out.get(nest_key), dict):
                out[nest_key] = _set_page_in_payload(out[nest_key], page_no, page_size)
        return out
    return payload


def _set_page_in_url(url: str, page_no: int, page_size: int | None = None) -> str:
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    page_keys = ("page", "page_num", "pageNum", "page_no", "pageNo", "current", "current_page", "currentPage")
    size_keys = ("pageSize", "page_size", "size", "limit")
    touched = False
    for key in page_keys:
        if key in query:
            query[key] = str(page_no)
            touched = True
    if page_size is not None:
        for key in size_keys:
            if key in query:
                query[key] = str(page_size)
                touched = True
    if not touched:
        query["pageNum"] = str(page_no)
        if page_size is not None:
            query.setdefault("pageSize", str(page_size))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _format_pdd_time(raw: Any) -> str:
    if raw in (None, ""):
        return ""
    if isinstance(raw, (int, float)) and raw > 10_000_000:
        seconds = raw
        if seconds >= 100_000_000_000:
            seconds = seconds / 1000.0
        try:
            return datetime.fromtimestamp(int(seconds), tz=SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(raw)
    text = str(raw).strip()
    if re.fullmatch(r"\d{10,13}", text):
        try:
            ts = int(text)
            if ts >= 100_000_000_000:
                ts = ts // 1000
            return datetime.fromtimestamp(ts, tz=SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return text
    return text


def _normalize_pdd_amount(raw: Any) -> str:
    """PDD 商家后台金额为分；统一转为元字符串（保留两位小数）。"""
    if raw in (None, ""):
        return ""
    try:
        value = float(raw)
    except Exception:
        return str(raw).strip()
    if _PDD_AMOUNT_IN_FEN and abs(value - round(value)) < 1e-9:
        value = value / 100.0
    return f"{value:.2f}"


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return ""


def _map_order_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a raw PDD order-list row to the Java ingest order contract."""
    order_no = str(_pick(raw, "order_sn", "orderSn", "order_no", "orderNo", "order_id", "orderId") or "").strip()
    goods_list = raw.get("goods_list") if isinstance(raw.get("goods_list"), list) else []
    if not goods_list:
        goods_list = raw.get("goodsList") if isinstance(raw.get("goodsList"), list) else []
    if not goods_list and raw.get("goods_name") not in (None, ""):
        # recentOrderList 返回扁平商品字段（无 goods_list 嵌套）
        goods_list = [
            {
                "goods_name": raw.get("goods_name"),
                "spec": raw.get("spec"),
                "goods_num": raw.get("goods_number"),
                "goods_amount": raw.get("goods_amount"),
                "goods_price": raw.get("goods_price"),
                "thumb_url": raw.get("thumb_url"),
            }
        ]

    product_names: list[str] = []
    sku_texts: list[str] = []
    quantities = 0
    item_amounts: list[float] = []
    unit_prices: list[float] = []
    image_url = ""
    for goods in goods_list:
        if not isinstance(goods, dict):
            continue
        name = str(_pick(goods, "goods_name", "goodsName", "product_name", "productName", "name") or "").strip()
        spec = str(_pick(goods, "spec", "sku_spec", "goods_spec", "sku_text", "skuText") or "").strip()
        if name:
            product_names.append(name)
        if spec:
            sku_texts.append(spec)
        try:
            quantities += int(_pick(goods, "goods_num", "goodsNum", "quantity", "num") or 1)
        except Exception:
            quantities += 1
        amount_raw = _pick(goods, "goods_amount", "goodsAmount", "pay_amount", "item_amount", "amount")
        if amount_raw not in (None, ""):
            try:
                item_amounts.append(float(_normalize_pdd_amount(amount_raw)))
            except Exception:
                pass
        price_raw = _pick(goods, "goods_price", "goodsPrice", "price", "unit_price", "unitPrice")
        if price_raw not in (None, ""):
            try:
                unit_prices.append(float(_normalize_pdd_amount(price_raw)))
            except Exception:
                pass
        if not image_url:
            image_url = str(_pick(goods, "goods_img", "goodsImg", "image", "img", "thumb_url", "thumbUrl") or "")

    pay_time_raw = _pick(raw, "pay_time", "payTime", "paid_at", "paidAt", "confirm_time", "confirmTime")
    pay_status_raw = _pick(raw, "pay_status", "payStatus")
    is_unpaid = pay_status_raw in (0, "0", False, "false") or pay_time_raw in (0, "0")
    pay_amount_raw = _pick(
        raw,
        "pay_amount",
        "payAmount",
        "order_amount",
        "orderAmount",
        "real_pay_amount",
        "actual_pay_amount",
    )
    pay_amount = (
        _normalize_pdd_amount(pay_amount_raw)
        if pay_amount_raw not in (None, "")
        else ""
    )
    if is_unpaid:
        pay_amount = "0"
    refund_amount = _normalize_pdd_amount(
        _pick(raw, "refund_amount", "refundAmount", "after_sale_amount", "refunded_amount", "refundedAmount")
    )
    status_raw = _pick(
        raw,
        "order_status_text",
        "orderStatusText",
        "order_status_str",
        "status_text",
        "statusText",
        "order_status_desc",
        "status_desc",
        "statusDesc",
        "status",
    )
    status = str(status_raw or "").strip()
    if not status:
        status = str(_pick(raw, "order_status", "orderStatus") or "").strip()
    ordered_at = _format_pdd_time(
        _pick(
            raw,
            "create_time",
            "createTime",
            "order_create_time",
            "orderCreateTime",
            "order_time",
            "orderTime",
            "pay_time",
            "payTime",
        )
    )
    paid_at = _format_pdd_time(pay_time_raw) if not is_unpaid else ""
    refunded_at = _format_pdd_time(_pick(raw, "refund_time", "refundTime", "refunded_at", "refundedAt"))
    buyer_masked = str(
        _pick(
            raw,
            "receive_name",
            "receiver_name",
            "receiverName",
            "buyer_masked",
            "buyerMasked",
            "buyer_name",
        )
        or ""
    )
    ship_deadline = _format_pdd_time(
        _pick(
            raw,
            "promise_shipping_time",
            "shipping_time",
            "ship_time",
            "shipTime",
            "ship_deadline",
            "deliver_deadline",
        )
    )
    channel = str(_pick(raw, "channel", "order_from", "orderFrom") or "拼多多").strip()
    report_day = str(_pick(raw, "report_day", "reportDay") or "")
    if not report_day and ordered_at:
        report_day = ordered_at[:10]

    item_amount_total = f"{sum(item_amounts):.2f}" if item_amounts else "0"
    amount_value = (
        item_amount_total
        if is_unpaid
        else (pay_amount or item_amount_total)
    )
    return {
        "order_no": order_no,
        "order_key": str(_pick(raw, "order_key", "orderKey") or f"pdd:{order_no}"),
        "external_shop_id": str(_pick(raw, "mall_id", "mallId", "external_shop_id") or ""),
        "product_name": " / ".join(dict.fromkeys(product_names)) if product_names else "",
        "channel": channel,
        "sku": " / ".join(dict.fromkeys(sku_texts)) if sku_texts else "",
        "sku_text": " / ".join(dict.fromkeys(sku_texts)) if sku_texts else "",
        "quantity": quantities,
        "amount": amount_value,
        "paid_amount": pay_amount,
        "refunded_amount": refund_amount,
        "unit_price": f"{sum(unit_prices) / max(1, len(unit_prices)):.2f}" if unit_prices else "",
        "item_amount": f"{sum(item_amounts):.2f}" if item_amounts else "",
        "currency": "CNY",
        "status": status,
        "ship_deadline": ship_deadline,
        "ordered_at": ordered_at,
        "paid_at": paid_at or ("" if is_unpaid else ordered_at),
        "refunded_at": refunded_at,
        "buyer_masked": buyer_masked,
        "image_url": image_url,
        "report_day": report_day,
        "raw_json": json.dumps(raw, ensure_ascii=False),
    }


def _map_product_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a raw PDD goods-list row to the Java product ingest contract."""
    product_id = str(
        _pick(raw, "goods_id", "goodsId", "product_id", "productId", "goods_sn", "goodsSn", "id") or ""
    ).strip()
    name = str(
        _pick(
            raw,
            "goods_name",
            "goodsName",
            "product_name",
            "productName",
            "name",
            "title",
            "goods_desc",
            "share_desc",
        )
        or ""
    ).strip()
    status_raw = _pick(
        raw,
        "is_onsale",
        "ware_status",
        "goods_status_text",
        "status_text",
        "statusText",
        "goods_status",
        "status",
    )
    if status_raw is True or str(status_raw or "").strip().lower() in ("1", "true", "on"):
        status = "在售"
    else:
        status = str(status_raw or "").strip()

    def first_money(*keys: str) -> Any:
        for key in keys:
            value = raw.get(key)
            if isinstance(value, list) and value:
                try:
                    return min(float(v) for v in value if v not in (None, ""))
                except Exception:
                    continue
            if value not in (None, ""):
                return value
        return ""

    price_raw = first_money("sku_group_price", "sku_price", "market_price", "suggest_price", "goods_price")
    image = _pick(raw, "thumb_url", "hd_thumb_url", "image_url", "hd_url", "goodsImage", "image", "img")
    skus = _pick(raw, "sku_list", "skus", "specs")
    cats = [str(raw.get(f"cat_name_{i}") or "").strip() for i in range(1, 5)]
    category = " / ".join(c for c in cats if c) or str(_pick(raw, "cat_name", "category") or "")
    return {
        "product_id": product_id,
        "product_key": str(_pick(raw, "goods_sn", "goodsSn", "product_key") or f"pdd:{product_id}"),
        "product_name": name,
        "status": status,
        "status_label": status,
        "price": _normalize_pdd_amount(price_raw) if price_raw not in (None, "") else None,
        "stock": _pick(raw, "quantity", "reserve_quantity", "stock_num", "stockNum", "stock"),
        "sales": _pick(
            raw,
            "sold_quantity_for_thirty_days",
            "sold_quantity",
            "soldQuantity",
            "sales",
            "sold_num",
            "soldNum",
        ),
        "main_image": str(image or ""),
        "category": category,
        "article_no": str(
            _pick(raw, "out_goods_sn", "goods_sn", "goodsSn", "article_no", "articleNo", "outer_goods_id") or ""
        ),
        "sku_count": len(skus) if isinstance(skus, list) else 0,
        "skus_json": json.dumps(skus, ensure_ascii=False) if isinstance(skus, (list, dict)) else "",
        "raw_json": json.dumps(raw, ensure_ascii=False),
    }


def _map_issue_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a raw PDD after-sale/violation row to the Java issues ingest contract."""
    issue_type = str(_pick(raw, "after_sale_type", "afterSaleType", "type") or "after_sale").strip()
    type_label = str(
        _pick(raw, "after_sale_type_text", "afterSaleTypeText", "type_text", "typeText") or ""
    ).strip()
    priority = str(_pick(raw, "priority", "level", "risk_level") or "medium").strip()
    reported_at = _format_pdd_time(
        _pick(raw, "create_time", "createTime", "after_sale_create_time", "reported_at", "apply_time", "applyTime")
    )
    product_name = str(
        _pick(raw, "goods_name", "goodsName", "product_name", "productName", "name") or ""
    ).strip()
    image = _pick(raw, "goods_img", "goodsImg", "image", "img", "thumb_url", "thumbUrl")
    detail = str(
        _pick(
            raw,
            "reason",
            "after_sale_reason",
            "afterSaleReason",
            "violation_reason",
            "detail",
            "message",
        )
        or ""
    ).strip()
    external_id = str(
        _pick(raw, "after_sale_id", "afterSaleId", "violation_id", "order_sn", "orderSn", "id") or ""
    ).strip()
    return {
        "external_id": external_id,
        "type": issue_type,
        "type_label": type_label,
        "sku": str(_pick(raw, "sku", "spec", "goods_spec") or ""),
        "product_name": product_name,
        "product_image": str(image or ""),
        "detail": detail,
        "priority": priority if priority.lower() in {"high", "medium", "low"} else "medium",
        "reported_at": reported_at,
        "source": "pdd",
        "raw_json": json.dumps(raw, ensure_ascii=False),
    }


def _extract_captured_rows(payload: Any, kind: str) -> list[dict[str, Any]]:
    rows = _find_list_rows(payload, kind) or []
    if kind == "orders":
        return [_map_order_row(r) for r in rows]
    if kind == "products":
        return [_map_product_row(r) for r in rows]
    if kind == "issues":
        return [_map_issue_row(r) for r in rows]
    return rows


def _order_rows_from_payload(data: Any) -> list[dict[str, Any]]:
    """Map order rows from a replay payload; empty list when no rows are found.

    ``_find_list_rows`` returns ``None`` when the payload has no recognizable
    order list (e.g. a rate-limit or error body), which used to crash the
    per-day fetch with ``'NoneType' object is not iterable``.
    """
    rows = _find_list_rows(data, "orders") or []
    return [_map_order_row(r) for r in rows]


_ORDER_LIST_EMPTY_HINTS = (
    "orderlist",
    "order_list",
    "orders",
    "pageitems",
    "resultlist",
    "rows",
    "items",
    "list",
)


def _looks_like_empty_order_list(data: Any) -> bool:
    """True when the payload carries an explicit（可能为空的）订单列表字段。"""
    if not isinstance(data, dict):
        return False
    for key, value in data.items():
        if isinstance(value, list):
            low = str(key).lower()
            if any(hint in low for hint in _ORDER_LIST_EMPTY_HINTS):
                return True
        elif isinstance(value, dict) and _looks_like_empty_order_list(value):
            return True
    return False


def _validate_order_response(data: Any) -> None:
    """Raise when the replay response is not a usable order-list payload.

    PDD 在签名过期/未登录/频控时可能返回 null 或错误体；这些必须按“失败日”处理，
    否则会被当成“今天没有订单”静默入库，导致同步显示成功但前端没有数据。
    """
    if data is None:
        raise RuntimeError("订单接口返回空响应（可能登录态失效或签名过期）")
    if not isinstance(data, dict):
        raise RuntimeError("订单接口返回非对象响应")
    if data.get("success") is False:
        msg = (
            data.get("error_msg")
            or data.get("errorMsg")
            or data.get("message")
            or "unknown"
        )
        raise RuntimeError(f"订单接口返回错误: {msg}")
    if _find_list_rows(data, "orders") is None and not _looks_like_empty_order_list(data):
        raise RuntimeError("订单接口响应中未发现订单列表（可能签名过期或触发频控）")


def _sanitize_utf8(value: Any) -> Any:
    """递归清理孤立代理字符（emoji 拆包等），避免 httpx 序列化时 UnicodeEncodeError。"""
    if isinstance(value, dict):
        return {k: _sanitize_utf8(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_utf8(v) for v in value]
    if isinstance(value, str):
        try:
            return value.encode("utf-8", errors="replace").decode("utf-8")
        except Exception:
            return value
    return value


def _capture_xhr(page, page_urls: tuple[str, ...], kind: str, *, timeout: float | None = None) -> dict[str, Any] | None:
    """Open the list page and capture the first matching JSON list XHR (runtime Day0)."""
    capture_timeout = PDD_XHR_CAPTURE_TIMEOUT_SECONDS if timeout is None else timeout
    captured: dict[str, Any] = {}
    started = time.perf_counter()

    def on_response(response) -> None:
        if captured:
            return
        try:
            request = response.request
            url = request.url or ""
            if not _looks_kind_api_url(url, kind):
                return
            if response.status >= 400:
                return
            if kind == "orders" and "recentorderlist" in (url or "").lower():
                # 跳过首屏“最近一笔”小组件调用（pageSize=1 + consolidateTypeList），
                # 等待订单列表主请求（pageSize>=20，无 consolidateTypeList）。
                post = request.post_data or ""
                try:
                    body = json.loads(post) if post else {}
                except Exception:  # noqa: BLE001
                    body = {}
                if isinstance(body, dict):
                    if body.get("consolidateTypeList"):
                        return
                    try:
                        page_size = int(body.get("pageSize") or 0)
                    except Exception:  # noqa: BLE001
                        page_size = 0
                    if page_size <= 1:
                        return
            payload = response.json()
        except Exception:
            return
        rows = _find_list_rows(payload, kind)
        if not rows:
            return
        captured["method"] = request.method
        captured["url"] = url
        captured["headers"] = dict(request.headers)
        captured["post_data"] = request.post_data
        captured["payload"] = payload
        captured["rows"] = rows

    page.on("response", on_response)
    try:
        last_error: Exception | None = None
        for page_url in page_urls:
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=PDD_XHR_NAV_TIMEOUT_MS)
                if "/other/404" in (page.url or ""):
                    continue
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue
        else:
            raise RuntimeError(f"无法打开 {page_urls[0]}: {last_error}")
        deadline = time.time() + capture_timeout
        while time.time() < deadline:
            if captured:
                print(
                    f"[PddPerf] capture_xhr kind={kind} elapsed={time.perf_counter() - started:.2f}s "
                    f"url={captured.get('url') or '-'}",
                    flush=True,
                )
                return captured
            page.wait_for_timeout(300)
    finally:
        try:
            page.remove_listener("response", on_response)
        except Exception:
            pass
    print(
        f"[PddPerf] capture_xhr kind={kind} miss elapsed={time.perf_counter() - started:.2f}s",
        flush=True,
    )
    return None


def _replay_page(
    page,
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    post_data: str | None,
    page_no: int,
    page_size: int,
    kind: str = "",
) -> dict[str, Any]:
    """Replay one page of a captured XHR with the same browser cookie jar."""
    method_u = (method or "GET").upper()
    req_headers = _pdd_replay_headers(kind, {"headers": headers or {}})
    body = post_data
    target_url = url
    if method_u == "GET":
        target_url = _set_page_in_url(url, page_no, page_size)
        body = None
    else:
        payload: Any = None
        if post_data:
            try:
                payload = json.loads(post_data)
            except Exception:
                payload = None
        if isinstance(payload, (dict, list)):
            payload = _set_page_in_payload(payload, page_no, page_size)
            body = json.dumps(payload, ensure_ascii=False)
        else:
            target_url = _set_page_in_url(url, page_no, page_size)
    print(f"[PddXhr] fetch page={page_no} {method_u} {target_url}", flush=True)
    with timed_stage("pdd_xhr.request"):
        response = page.request.fetch(
            target_url,
            method=method_u,
            headers=req_headers,
            data=body,
            timeout=PDD_XHR_REPLAY_TIMEOUT_MS,
        )
    if response.status >= 400:
        raise RuntimeError(f"page {page_no} HTTP {response.status}")
    try:
        payload = response.json()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"page {page_no} invalid json: {exc}") from exc
    if isinstance(payload, dict):
        error_code = payload.get("error_code") or payload.get("errorCode")
        error_msg = str(payload.get("error_msg") or payload.get("errorMsg") or "")
        if error_code in (40002, 4000106) or "频繁" in error_msg or "稍后再试" in error_msg:
            raise RuntimeError(
                f"page {page_no} 触发平台频控: {error_msg or error_code}"
            )
    return payload


def _is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc)
    return "频控" in text or "频繁" in text or "稍后再试" in text


def _is_transient_transport_error(exc: Exception) -> bool:
    text = str(exc).lower()
    if any(marker in text for marker in ("timeout", "network", "connection", "temporar")):
        return True
    return bool(re.search(r"\bhttp\s+(?:408|5\d\d)\b", text))


def _replay_with_retry(
    page,
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    post_data: str | None,
    page_no: int,
    page_size: int,
    kind: str = "",
    retries: int = 2,
    base_delay: float = 10.0,
) -> dict[str, Any]:
    """Replay one page with long rate-limit and short transport recovery paths."""
    last_exc: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            return _replay_page(
                page,
                method=method,
                url=url,
                headers=headers,
                post_data=post_data,
                page_no=page_no,
                page_size=page_size,
                kind=kind,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt + 1 < retries and _is_rate_limit_error(exc):
                delay = base_delay * (2 ** attempt) + random.uniform(1, 4)
                print(
                    f"[PddXhr] page={page_no} 频控，{int(delay)}s 后重试",
                    flush=True,
                )
                with timed_stage("pdd_xhr.retry_wait"):
                    time.sleep(delay)
                continue
            if attempt + 1 < retries and _is_transient_transport_error(exc):
                delay = min(3.0, 1.0 * (2 ** attempt))
                print(
                    f"[PddXhr] page={page_no} network failure; retry in {delay:.1f}s: {exc}",
                    flush=True,
                )
                with timed_stage("pdd_xhr.retry_wait"):
                    time.sleep(delay)
                continue
            raise
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"page {page_no} replay failed")


def _pdd_xhr_cache_path() -> Path:
    # 优先存到 profile 根目录（源码=backend/python，冻结版=工作树 backend/python），
    # 避免 Helper 重新打包把 _internal 里的缓存清掉。
    try:
        return Path(_pdd_profile_root()) / _PDD_XHR_CACHE_NAME
    except Exception:  # noqa: BLE001
        return ROOT / _PDD_XHR_CACHE_NAME


def _load_pdd_xhr_cache(kind: str) -> dict[str, Any]:
    try:
        data = json.loads(_pdd_xhr_cache_path().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    entry = data.get(kind) if isinstance(data, dict) else None
    if not isinstance(entry, dict):
        return {}
    headers = entry.get("headers")
    post_data = entry.get("post_data")
    return {
        "method": str(entry.get("method") or "POST"),
        "url": str(entry.get("url") or "").strip(),
        "headers": headers if isinstance(headers, dict) else {},
        "post_data": str(post_data) if post_data else "",
        "updated_at": str(entry.get("updated_at") or ""),
        "last_page": int(entry.get("last_page") or 0),
        "failed_days": entry.get("failed_days")
        if isinstance(entry.get("failed_days"), list)
        else [],
        "window": str(entry.get("window") or ""),
    }


def _save_pdd_xhr_cache(kind: str, captured: dict[str, Any]) -> None:
    url = str(captured.get("url") or "").strip()
    if not url:
        return
    path = _pdd_xhr_cache_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:  # noqa: BLE001
        data = {}
    if not isinstance(data, dict):
        data = {}
    data[kind] = {
        "method": str(captured.get("method") or "POST"),
        "url": url,
        "headers": captured.get("headers") if isinstance(captured.get("headers"), dict) else {},
        "post_data": str(captured.get("post_data") or ""),
        "updated_at": datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:  # noqa: BLE001
        print(f"[PddXhr] cache write failed: {exc}", flush=True)


def _save_pdd_last_page(kind: str, last_page: int) -> None:
    """把已成功翻到的最后一页写入缓存，下次同步从该页续抓，避免重复请求。"""
    path = _pdd_xhr_cache_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:  # noqa: BLE001
        data = {}
    if not isinstance(data, dict):
        data = {}
    entry = data.setdefault(kind, {})
    entry["last_page"] = int(last_page or 0)
    entry["updated_at"] = datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:  # noqa: BLE001
        print(f"[PddXhr] cache write failed: {exc}", flush=True)


def _save_pdd_failed_days(kind: str, date_window: str, failed_days: list[str]) -> None:
    """持久化失败日，下次同步只补失败日+今天，逐轮补齐完整窗口。"""
    window = str(date_window or "today").strip().lower()
    if window in ("today", "d1", "d7", "d30", "d90"):
        allowed = set(_window_day_list(window))
    else:
        allowed = None
    path = _pdd_xhr_cache_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:  # noqa: BLE001
        data = {}
    if not isinstance(data, dict):
        data = {}
    entry = data.setdefault(kind, {})
    failed = list(dict.fromkeys(failed_days or []))
    if allowed is not None:
        failed = [d for d in failed if d in allowed]
    failed.sort(reverse=True)
    entry["failed_days"] = failed
    entry["window"] = window
    entry["updated_at"] = datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:  # noqa: BLE001
        print(f"[PddXhr] cache write failed: {exc}", flush=True)


def _try_direct_first_page(
    page,
    kind: str,
    api_candidates: tuple[str, ...],
    cached: dict[str, Any],
) -> dict[str, Any] | None:
    """Try the cached/hardcoded endpoint WITHOUT opening the list page.

    优先用缓存里保存的完整请求规格（headers + post_data，含平台签名）直接重放；
    无缓存规格时才退化为纯 POST 探测。只有本函数全部失败才允许 _capture_xhr 开页。
    """
    urls: list[str] = []
    cached_url = str(cached.get("url") or "").strip()
    if cached_url:
        urls.append(cached_url)
    urls.extend(str(u) for u in api_candidates)
    seen_urls: set[str] = set()
    for api in urls:
        if not api or api in seen_urls:
            continue
        seen_urls.add(api)
        cached_post = str(cached.get("post_data") or "")
        body = None
        headers = _pdd_replay_headers(kind, cached)
        if cached_post:
            body = _normalize_orders_post_data(cached_post) if kind == "orders" else cached_post
        try:
            post_data = body if body is not None else json.dumps({"pageNum": 1, "pageSize": 100})
            resp = page.request.post(
                api,
                headers=headers,
                data=post_data,
                timeout=PDD_XHR_DIRECT_TIMEOUT_MS,
            )
            if resp.status >= 400:
                continue
            payload = resp.json()
            rows = _find_list_rows(payload, kind)
            if not rows:
                continue
            replayed_post = _set_page_in_payload(
                json.loads(post_data) if isinstance(post_data, str) else {},
                1,
                100,
            )
            return {
                "method": "POST",
                "url": api,
                "headers": headers,
                "post_data": json.dumps(replayed_post, ensure_ascii=False)
                if isinstance(replayed_post, dict)
                else post_data,
                "payload": payload,
                "rows": rows,
                "_direct": True,
            }
        except Exception:  # noqa: BLE001
            continue
    return None


def _fetch_paged_rows(
    page,
    *,
    kind: str,
    page_urls: tuple[str, ...],
    api_candidates: tuple[str, ...],
    date_window: str = "today",
    store_id: str | None = None,
    skip_direct: bool = False,
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    if page is None:
        raise RuntimeError(
            f"PDD_{kind.upper()}_SOURCE_UNAVAILABLE: 需要已登录的拼多多商家后台浏览器会话"
        )

    # 优先用冻结/候选接口直接拉第一页（不开页面、不点击）；失败再运行时发现。
    cached = {} if skip_direct else _load_pdd_xhr_cache(kind)
    captured = None if skip_direct else _try_direct_first_page(page, kind, api_candidates, cached)
    if captured is None:
        captured = _capture_xhr(page, page_urls, kind)
        if captured:
            _save_pdd_xhr_cache(kind, captured)
    elif not cached.get("url"):
        # 第一次通过候选接口直连成功：冻结该接口，后续同步直接复用。
        _save_pdd_xhr_cache(kind, captured)
    if captured is None:
        raise RuntimeError(
            f"PDD_{kind.upper()}_SOURCE_UNAVAILABLE: 未能在拼多多商家后台发现 {kind} 列表接口，"
            "请确认已登录且页面已打开"
        )

    source_url = str(captured.get("url") or page_urls[0])
    method = str(captured.get("method") or "POST")
    url = str(captured.get("url") or "")
    headers = captured.get("headers") or {}
    post_data = captured.get("post_data")
    first_payload = captured.get("payload") or {}

    # 订单列表：把捕获到的 recentOrderList 强制改成“全部订单”查询（orderType=0），
    # 并重放第一页作为基准（页面默认是“待发货”Tab，orderType=1）。
    # 商品分页默认 50/页（PDD_PRODUCTS_PAGE_SIZE 可调）；平台若忽略 pageSize，
    # 分页循环按实际返回行数自适应，不会提前截断。
    target_page_size = 50 if kind == "orders" else (
        int(os.getenv("PDD_PRODUCTS_PAGE_SIZE", "50") or "0") or None
    )
    if kind == "orders" and "recentorderlist" in url.lower():
        normalized = _normalize_orders_post_data(post_data)
        if normalized:
            post_data = normalized
            # 直连成功（_direct）时首页已是“全部订单”查询，无需再重放一次；
            # 只有来自页面抓包（默认“待发货”Tab）时才需要重放首页并归一化。
            if not captured.get("_direct"):
                time.sleep(1.0)
                try:
                    first_payload = _replay_with_retry(
                        page,
                        method=method,
                        url=url,
                        headers=headers,
                        post_data=post_data,
                        page_no=1,
                        page_size=target_page_size,
                        kind=kind,
                    )
                except Exception as exc:  # noqa: BLE001
                    raise RuntimeError(
                        "PDD_ORDERS_SOURCE_UNAVAILABLE: 订单列表接口重放失败"
                        f"（可能触发平台频控），请稍后再试：{exc}。"
                    ) from exc

    first_rows = _extract_captured_rows(first_payload, kind)
    all_rows: list[dict[str, Any]] = list(first_rows)
    total_hint = _extract_total_count(first_payload, len(first_rows))
    meta: dict[str, Any] = {
        "total_hint": total_hint,
        # 分页循环因平台频控重试耗尽而中断时置位，用于把任务标记为 partial
        # （仅“抓取中断”才算不完整；翻到窗口起点的正常停止不算）。
        "truncated": False,
        "last_page": 1,
    }

    # 请求 pageSize 用目标值（平台可能忽略并按实际上限返回）；
    # 翻页上限按“实际返回行数”计算，避免平台忽略 pageSize 时提前停止。
    page_size = target_page_size or max(1, len(first_rows))
    step = max(1, len(first_rows))
    cached_last = int(cached.get("last_page") or 0) if isinstance(cached, dict) else 0
    page_no = max(2, cached_last + 1)
    max_pages = max(
        1,
        min(
            200,
            (max(total_hint, 1) + step - 1) // step + 2,
        ),
    )
    window_start = ""
    if kind == "orders":
        window = str(date_window or "today").strip().lower()
        if window in ("today", "d1", "d7", "d30", "d90"):
            window_start = _window_day_list(window)[0]
    while page_no < max_pages and len(all_rows) < max(total_hint, 1):
        if kind == "orders" and window_start and any(
            str(r.get("report_day") or "")[:10] < window_start
            for r in all_rows
        ):
            # 已越过窗口起点（列表按下单时间倒序），无需继续翻页。
            break
        try:
            payload = _replay_with_retry(
                page,
                method=method,
                url=url,
                headers=headers,
                post_data=post_data,
                page_no=page_no,
                page_size=page_size,
                kind=kind,
            )
        except Exception as exc:  # noqa: BLE001
            if (
                kind in ("orders", "products")
                and page_no == 2
                and not _is_rate_limit_error(exc)
            ):
                raise RuntimeError(
                    f"PDD_{kind.upper()}_SOURCE_UNAVAILABLE: 接口拒绝修改页码参数"
                    f"（可能受 anti-content 签名限制）：{exc}。"
                    "请确认列表接口的页码字段（pageNum/pageNo/page）后再试"
                ) from exc
            print(f"[PddXhr] {kind} page={page_no} failed: {exc}", flush=True)
            meta["truncated"] = True
            break
        batch = _extract_captured_rows(payload, kind)
        if not batch:
            break
        all_rows.extend(batch)
        meta["last_page"] = page_no
        if kind == "orders" and window_start:
            # 列表按下单时间倒序；一旦越过窗口起点即可停止，避免把 90 天全量拉完。
            batch_days = [str(r.get("report_day") or "")[:10] for r in batch]
            if any(d and d < window_start for d in batch_days):
                break
        if not batch:
            break
        page_no += 1
        time.sleep(_pdd_page_sleep(kind))

    if kind in ("orders", "products"):
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for row in all_rows:
            if kind == "orders":
                key = str(row.get("order_key") or "") or str(row.get("order_no") or "")
            else:
                key = str(row.get("product_key") or "") or str(row.get("product_id") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(row)
        all_rows = unique
    print(f"[PddXhr] {kind} rows={len(all_rows)} total_hint={total_hint} source={url}", flush=True)
    return all_rows, source_url, meta


def fetch_orders_via_xhr(
    page,
    *,
    date_window: str = "today",
    store_id: str | None = None,
    on_day=None,
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    """按天分窗直接重放订单接口：不开页面、不抓包，逐天完整且独立成败。"""
    if page is None:
        raise RuntimeError(
            "PDD_ORDERS_SOURCE_UNAVAILABLE: need a logged-in PDD seller browser session"
        )
    cached = _load_pdd_xhr_cache("orders")
    cached_failed = cached.get("failed_days") if isinstance(cached, dict) else []
    cached_window = str(cached.get("window") or "") if isinstance(cached, dict) else ""
    days_to_fetch: list[str] | None = None
    window = str(date_window or "today").strip().lower()
    if cached_failed and cached_window == window:
        window_days = set(_window_day_list(window))
        days_to_fetch = [d for d in dict.fromkeys([*cached_failed, _today_str()]) if d in window_days]
        days_to_fetch.sort(reverse=True)
    spec: dict[str, Any] | None = None
    if cached.get("url") and cached.get("post_data"):
        # 已有完整请求规格（签名头/body）：直接按天重放，不再探测或开页。
        spec = cached
    else:
        spec = _try_direct_first_page(page, "orders", PDD_ORDER_LIST_API_CANDIDATES, cached)
        if spec is None:
            spec = _capture_xhr(page, PDD_ORDER_LIST_PAGE_CANDIDATES, "orders")
            if spec:
                _save_pdd_xhr_cache("orders", spec)
    if spec is None:
        raise RuntimeError(
            "PDD_ORDERS_SOURCE_UNAVAILABLE: 未能在拼多多商家后台发现订单列表接口，"
            "请确认已登录且页面已打开"
        )
    url = str(spec.get("url") or "")
    headers = spec.get("headers") or {}
    post_data = str(spec.get("post_data") or "")
    if "recentorderlist" in url.lower():
        normalized = _normalize_orders_post_data(post_data)
        if normalized:
            post_data = normalized
    rows, meta = _fetch_orders_by_day(
        page,
        url=url,
        headers=headers,
        post_data=post_data,
        date_window=date_window,
        days=days_to_fetch,
        on_day=on_day,
    )
    if meta.get("failed_days"):
        # 接口被拒/频控：重新抓包刷新签名后仅补失败日（规则允许的兜底）。
        fresh = _capture_xhr(page, PDD_ORDER_LIST_PAGE_CANDIDATES, "orders")
        if fresh:
            _save_pdd_xhr_cache("orders", fresh)
            fresh_url = str(fresh.get("url") or "")
            fresh_post = str(fresh.get("post_data") or "")
            if "recentorderlist" in fresh_url.lower():
                normalized = _normalize_orders_post_data(fresh_post)
                if normalized:
                    fresh_post = normalized
            retry_rows, retry_meta = _fetch_orders_by_day(
                page,
                url=fresh_url,
                headers=fresh.get("headers") or {},
                post_data=fresh_post,
                date_window=date_window,
                days=meta["failed_days"],
                on_day=on_day,
            )
            rows.extend(retry_rows)
            meta["failed_days"] = retry_meta.get("failed_days") or []
            meta["truncated"] = bool(meta["failed_days"])
            meta["total_hint"] = int(meta.get("total_hint") or 0) + int(
                retry_meta.get("total_hint") or 0
            )
    _save_pdd_failed_days("orders", date_window, meta.get("failed_days") or [])
    return rows, url, meta


def fetch_products_via_xhr(
    page,
    *,
    store_id: str | None = None,
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    """直接从 mms.pinduoduo.com 商品列表接口抓取全部商品。返回 (rows, source_url)。"""
    return _fetch_paged_rows(
        page,
        kind="products",
        page_urls=PDD_PRODUCT_LIST_PAGE_CANDIDATES,
        api_candidates=PDD_PRODUCT_LIST_API_CANDIDATES,
        store_id=store_id,
    )


_PDD_COMPASS_TRADE_KEYS = ("payOrdrAmt", "payOrdrCnt", "payOrdrUsrCnt")


def _normalize_pdd_compass_payload(
    captured: dict[str, Any],
    *,
    date_type: int,
    store_id: str | None,
) -> dict[str, Any]:
    """把数据中心 sydney/api 报文整理成罗盘快照。

    getMallTradeInfo 的金额/单数字段使用自定义字体混淆（私有区字符），
    无法可靠还原成数字，因此原样保留；同时把能拿到的实数字段
    （未支付订单、地理分布确认订单合计）一并写入，供展示与核对。
    """
    payload = captured.get("payload") or {}
    result = payload.get("result") if isinstance(payload, dict) else {}
    if not isinstance(result, dict):
        result = {}
    extras = captured.get("extra") or []
    not_pay: dict[str, Any] = {}
    geo_rows: list[dict[str, Any]] = []
    for extra in extras:
        extra_payload = extra.get("payload") or {}
        extra_result = extra_payload.get("result") if isinstance(extra_payload, dict) else {}
        if not isinstance(extra_result, dict):
            continue
        if "notPayOrderCnt" in extra_result:
            not_pay = extra_result
        rows = extra_result.get("geographyDistributionVOList")
        if isinstance(rows, list):
            geo_rows = [r for r in rows if isinstance(r, dict)]

    now = datetime.now(SHANGHAI)
    today = now.strftime("%Y-%m-%d")
    label = {1: "实时", 20: "近1天", 21: "近7天", 23: "近30天"}.get(date_type, "实时")
    out: dict[str, Any] = {
        "date_type": date_type,
        "date_label": label,
        "store_id": store_id or "",
        "report_day": today,
        "source_url": str(captured.get("url") or PDD_COMPASS_PAGE),
        "synced_at": now.isoformat(),
        "raw_trade": result,
    }
    for key in (
        "payOrdrAmt",
        "payOrdrCnt",
        "payOrdrUsrCnt",
        "payOrdrAup",
        "payUvRto",
        "rpayUsrRtoDth",
        "sucRfOrdrAmt1d",
        "sucRfOrdrCnt1d",
        "mallFavCnt",
        "uvCfmVal",
    ):
        if key in result:
            out[key] = result[key]
    if not_pay:
        out["not_pay_order_count"] = not_pay.get("notPayOrderCnt")
        out["not_pay_order_amount"] = not_pay.get("notPayOrderAmountCnt")
        out["settlement_shipping_amount"] = not_pay.get("settlementShippingAmount")
    if geo_rows:
        out["confirmed_pay_amount"] = round(
            sum(float(r.get("cfmOrdrAmt") or 0) for r in geo_rows), 2
        )
        out["confirmed_pay_count"] = sum(int(r.get("cfmOrdrCnt") or 0) for r in geo_rows)
        out["confirmed_pay_user_count"] = sum(
            int(r.get("cfmOrdrUsrCnt") or 0) for r in geo_rows
        )
        out["confirmed_stat_date"] = str(geo_rows[0].get("statDate") or "")
    return out


def fetch_compass_via_xhr(
    page,
    *,
    date_type: int = 1,
    store_id: str | None = None,
) -> tuple[dict[str, Any], str]:
    """从拼多多数据中心（/sycm/stores_data）抓取经营罗盘核心指标。

    返回 (normalized_payload, source_url)。真实接口为 mms.pinduoduo.com/sydney/api/*，
    例如 getMallTradeInfo（核心指标，字体混淆）、getMallNotPayOrderInfoV2（实数字段）、
    queryMallGeographyDistributionList（按省份确认订单，实数字段）。
    """
    if page is None:
        raise RuntimeError("PDD_COMPASS_SOURCE_UNAVAILABLE: 需要已登录的拼多多商家后台浏览器会话")
    captured: dict[str, Any] = {}

    def on_response(response) -> None:
        if captured.get("payload"):
            return
        try:
            url = response.request.url or ""
            if not _looks_kind_api_url(url, "compass"):
                return
            if response.status >= 400:
                return
            payload = response.json()
        except Exception:  # noqa: BLE001
            return
        if not isinstance(payload, dict):
            return
        result = payload.get("result")
        if not isinstance(result, dict):
            return
        if any(k in result for k in _PDD_COMPASS_TRADE_KEYS):
            captured["payload"] = payload
            captured["url"] = url
            captured["method"] = response.request.method
            captured["headers"] = dict(response.request.headers)
            captured["post_data"] = response.request.post_data
        elif "geographyDistributionVOList" in result or "notPayOrderCnt" in result:
            captured.setdefault("extra", []).append({"url": url, "payload": payload})

    page.on("response", on_response)
    try:
        last_error: Exception | None = None
        for page_url in PDD_COMPASS_PAGE_CANDIDATES:
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=PDD_XHR_NAV_TIMEOUT_MS)
                if "/other/404" in (page.url or ""):
                    continue
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue
        else:
            raise RuntimeError(f"无法打开 {PDD_COMPASS_PAGE_CANDIDATES[0]}: {last_error}")
        deadline = time.time() + PDD_XHR_CAPTURE_TIMEOUT_SECONDS
        while time.time() < deadline and not captured.get("payload"):
            page.wait_for_timeout(300)
    finally:
        try:
            page.remove_listener("response", on_response)
        except Exception:  # noqa: BLE001
            pass
    if not captured.get("payload"):
        raise RuntimeError(
            "PDD_COMPASS_SOURCE_UNAVAILABLE: 未能在数据中心捕获 sydney/api 罗盘接口，请确认已登录"
        )
    source_url = str(captured.get("url") or PDD_COMPASS_PAGE)
    payload = _normalize_pdd_compass_payload(
        captured, date_type=date_type, store_id=store_id
    )
    return payload, source_url
def fetch_issues_via_xhr(
    page,
    *,
    store_id: str | None = None,
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    """从 mms.pinduoduo.com 售后/违规页抓取问题预警列表。返回 (rows, source_url)。"""
    return _fetch_paged_rows(
        page,
        kind="issues",
        page_urls=PDD_ISSUE_LIST_PAGE_CANDIDATES,
        api_candidates=(),
        store_id=store_id,
    )


# ============================================================================
# 同步任务（对齐抖音 run_*_sync，回写 Java ingest）
# ============================================================================

def _resolve_store_id(client, tenant_id: int, store_id: str) -> str:
    store_id = (store_id or "").strip()
    if store_id:
        return store_id
    return _default_pdd_store_id(client, tenant_id) or "default"


def _list_pdd_store_ids(client, tenant_id: int) -> list[str]:
    """Return bound PDD store ids (bound_at desc order)."""
    try:
        accounts = client.list_platform_accounts(tenant_id) or {}
    except Exception:
        accounts = {}
    pdd = accounts.get("pdd") or accounts.get("items") or []
    if not isinstance(pdd, list):
        return []
    ids: list[str] = []
    for account in pdd:
        if not isinstance(account, dict):
            continue
        store_id = str(account.get("id") or "").strip()
        if store_id:
            ids.append(store_id)
    return ids


def _resolve_sync_store_ids(client, tenant_id: int, store_id: str) -> list[str]:
    """Single store id when requested; otherwise every bound PDD store."""
    store_id = (store_id or "").strip()
    if store_id and store_id.lower() != "all":
        return [store_id]
    ids = _list_pdd_store_ids(client, tenant_id)
    return ids if ids else ["default"]


def _default_pdd_store_id(client, tenant_id: int) -> str:
    """默认店铺 = 最早绑定的拼多多店铺（列表按绑定时间倒序，取最后一项）。"""
    try:
        accounts = client.list_platform_accounts(tenant_id) or {}
    except Exception:
        accounts = {}
    pdd = accounts.get("pdd") or accounts.get("items") or []
    if isinstance(pdd, list) and pdd:
        return str(pdd[-1].get("id") or "").strip()
    return ""


def _resolve_profile_store_id(client, tenant_id: int, store_id: str) -> str:
    """浏览器 profile 使用的店铺 key（对齐 1688）：默认/第一个店铺沿用平铺 profile，
    从第二个店铺起才使用独立 ``account-{store_id}`` profile。"""
    store_id = (store_id or "").strip()
    if not store_id:
        return "default"
    default_id = _default_pdd_store_id(client, tenant_id)
    if default_id and store_id == default_id:
        return "default"
    return store_id


def _today_str() -> str:
    return datetime.now(SHANGHAI).strftime("%Y-%m-%d")


def _day_epoch_bounds(day_iso: str) -> tuple[int, int]:
    """返回某天（Asia/Shanghai）的 [00:00, 次日00:00) 秒级时间戳。"""
    day = datetime.strptime(day_iso, "%Y-%m-%d").replace(tzinfo=SHANGHAI)
    start = int(day.timestamp())
    return start, start + 86400


def _window_day_list(date_window: str) -> list[str]:
    """按 date_window 生成需要覆盖的日期列表（含今天）。"""
    today = datetime.now(SHANGHAI).date()
    window = str(date_window or "today").strip().lower()
    if window == "d1":
        offset = 1
    elif window == "d7":
        offset = 6
    elif window == "d30":
        offset = 29
    elif window == "d90":
        offset = 89
    else:
        offset = 0
    return [(today - timedelta(days=offset - i)).isoformat() for i in range(offset + 1)]


def _fetch_orders_by_day(
    page,
    *,
    url: str,
    headers: dict[str, str],
    post_data: str,
    date_window: str,
    days: list[str] | None = None,
    on_day=None,
    bucket: TokenBucket | None = None,
    max_consecutive_failures: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """按天分窗抓取订单：每天 1 页即完整，逐天独立成败，避免全窗口翻页触发频控。

    某天被限流时标记 failed_days 并继续后续日期；下次同步可只补失败日。
    返回 (rows, meta)，meta 含 total_hint / truncated / failed_days。
    """
    day_list = days if days is not None else _window_day_list(date_window)
    # 从今天开始逐天往前抓：今天 → 昨天 → …（用户预期顺序，也让今日数据最先入库）
    day_list = list(dict.fromkeys(day_list))
    day_list.sort(key=lambda d: d, reverse=True)
    page_size = int(os.getenv("PDD_ORDERS_PAGE_SIZE", "50") or "50")
    retry_delay = float(os.getenv("PDD_DAY_RETRY_DELAY", "3") or "3")
    request_timeout = int(os.getenv("PDD_DAY_REQUEST_TIMEOUT_SECONDS", "20") or "20")
    if max_consecutive_failures is None:
        max_consecutive = int(
            os.getenv("PDD_DAY_MAX_CONSECUTIVE_FAILURES", "4") or "4"
        )
    else:
        max_consecutive = max(1, int(max_consecutive_failures))
    pacing_bucket = bucket if bucket is not None else _PDD_DAY_BUCKET
    base_payload: dict[str, Any] = {}
    try:
        parsed = json.loads(post_data)
        if isinstance(parsed, dict):
            base_payload = parsed
    except Exception:  # noqa: BLE001
        base_payload = {}

    all_rows: list[dict[str, Any]] = []
    meta: dict[str, Any] = {
        "total_hint": 0,
        "truncated": False,
        "last_page": 1,
        "failed_days": [],
    }
    req_headers = _pdd_replay_headers("orders", {"headers": headers})
    consecutive = 0
    for day_iso in day_list:
        start_ts, end_ts = _day_epoch_bounds(day_iso)
        payload = dict(base_payload)
        payload["groupStartTime"] = start_ts
        payload["groupEndTime"] = end_ts - 1
        payload["pageNumber"] = 1
        payload["pageSize"] = page_size
        body = json.dumps(payload, ensure_ascii=False)
        day_ok = False
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                with timed_stage("pdd_orders_day.request"):
                    resp = page.request.post(
                        url,
                        headers=req_headers,
                        data=body,
                        timeout=request_timeout * 1000,
                    )
                if resp.status >= 400:
                    raise RuntimeError(f"HTTP {resp.status}")
                data = resp.json()
                _validate_order_response(data)
                rows = _order_rows_from_payload(data)
                for row in rows:
                    if not str(row.get("report_day") or "")[:10]:
                        row["report_day"] = day_iso
                total = _extract_total_count(data, len(rows))
                all_rows.extend(rows)
                meta["total_hint"] += total
                meta["last_page"] = day_list.index(day_iso) + 1
                day_ok = True
                if callable(on_day):
                    try:
                        on_day(day_iso, rows, url)
                    except Exception as exc:  # noqa: BLE001
                        print(
                            f"[PddXhr] orders day={day_iso} ingest failed: {exc}",
                            flush=True,
                        )
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt == 0 and _is_rate_limit_error(exc):
                    time.sleep(retry_delay)
                    continue
                break
        if not day_ok:
            meta["failed_days"].append(day_iso)
            meta["truncated"] = True
            consecutive += 1
            print(
                f"[PddXhr] orders day={day_iso} failed: {last_exc}",
                flush=True,
            )
        else:
            consecutive = 0
        pacing_bucket.consume()
        if consecutive >= max_consecutive:
            remaining = day_list[day_list.index(day_iso) + 1 :]
            if remaining:
                meta["failed_days"].extend(remaining)
                meta["truncated"] = True
                print(
                    f"[PddXhr] orders abort after {consecutive} consecutive failures; "
                    f"{len(remaining)} days pending for next sync",
                    flush=True,
                )
            break
    return all_rows, meta


def _build_days_payload(orders: list[dict[str, Any]], date_window: str) -> list[dict[str, Any]]:
    """按订单实际日期（report_day）分组，覆盖抓取到的全部日期，供 Java ingest 按天替换。"""
    by_day: dict[str, list[dict[str, Any]]] = {}
    for row in orders:
        day = str(row.get("report_day") or "").strip() or _today_str()
        by_day.setdefault(day, []).append(row)
    return [{"replace_day": day, "orders": by_day[day]} for day in sorted(by_day)]


_PDD_CONTEXT_CACHE: dict[str, dict[str, Any]] = {}
_PDD_CONTEXT_CACHE_MAX = 2
_PDD_CONTEXT_IDLE_SECONDS = 300.0


def _pdd_context_key(tenant_id: int, profile_store: str) -> str:
    return f"pdd:{int(tenant_id)}:{normalize_session_key(profile_store)}"


def _pdd_context_thread_key(tenant_id: int, profile_store: str) -> tuple[int, str]:
    # Playwright sync 对象绑定创建线程；缓存按线程隔离，避免跨线程复用报
    # “Sync API inside the asyncio loop”错误。
    return (threading.get_ident(), _pdd_context_key(tenant_id, profile_store))


def _evict_pdd_contexts() -> None:
    """回收空闲超时或超出上限的持久化浏览器上下文（仅无头同步会话）。"""
    now = time.time()
    for key in list(_PDD_CONTEXT_CACHE):
        entry = _PDD_CONTEXT_CACHE[key]
        idle = now - entry.get("last_used", 0)
        if idle > _PDD_CONTEXT_IDLE_SECONDS or len(_PDD_CONTEXT_CACHE) > _PDD_CONTEXT_CACHE_MAX:
            _close_pw(entry.get("pw"), entry.get("context"))
            _PDD_CONTEXT_CACHE.pop(key, None)


def _release_pdd_session(pw, context) -> None:
    """同步结束把浏览器放回缓存复用；不在缓存中的会话直接关闭。"""
    key = getattr(context, "_pdd_cache_key", None)
    entry = _PDD_CONTEXT_CACHE.get(key) if key else None
    if entry is not None and entry.get("context") is context:
        entry["last_used"] = time.time()
        return
    _close_pw(pw, context)


def _open_pdd_session(
    client,
    tenant_id: int,
    store_id: str,
    *,
    wait_login: bool,
    label: str,
):
    """Open the store profile and return (pw, context, page), or None when skipping."""
    profile_store = _resolve_profile_store_id(client, tenant_id, store_id)
    # 拼多多同步统一无头：登录/会话探测仍走有头窗口，同步不弹浏览器。
    headless = True
    pw = context = page = None
    try:
        key = _pdd_context_thread_key(tenant_id, profile_store)
        entry = _PDD_CONTEXT_CACHE.get(key)
        if entry is not None:
            try:
                context_closed = entry["context"].is_closed()
            except Exception:  # noqa: BLE001
                context_closed = True
            if context_closed:
                _PDD_CONTEXT_CACHE.pop(key, None)
                entry = None
        if entry is not None:
            # 复用同一持久化浏览器（多标签页模式）：关闭旧页，新开一页进首页。
            pw, context = entry["pw"], entry["context"]
            context._pdd_cache_key = key  # type: ignore[attr-defined]
            entry["last_used"] = time.time()
            try:
                for p in list(context.pages):
                    p.close()
            except Exception:  # noqa: BLE001
                pass
            page = context.new_page()
            page.goto(PDD_SELLER_HOME, wait_until="domcontentloaded", timeout=PDD_SELLER_HOME_TIMEOUT_MS)
        else:
            # 无头同步使用主 profile 的临时副本，避免平台让无头会话失效时把
            # 主 profile 的登录 cookie 覆盖成登出状态（否则每次同步都要重新登录）。
            sync_profile = _clone_pdd_profile(profile_dir(tenant_id, profile_store)) if headless else None
            pw, context, page = _launch(
                tenant_id,
                headless=headless,
                force_navigate=True,
                store_id=profile_store,
                profile_dir_override=sync_profile,
            )
            context._pdd_cache_key = key  # type: ignore[attr-defined]
            if sync_profile is not None:
                # 副本会话随缓存复用/回收；主 profile 登录态始终不受无头同步影响
                context._pdd_sync_profile_tmp = sync_profile  # type: ignore[attr-defined]
            _PDD_CONTEXT_CACHE[key] = {
                "pw": pw,
                "context": context,
                "last_used": time.time(),
            }
            _evict_pdd_contexts()
        if not _looks_logged_in(page, context) and _has_auth_cookies(context):
            # 登录 cookie 有效但商家后台 SPA 尚未渲染完（启动瞬间 body 为空），
            # 等待页面渲染稳定再判定，避免把有效会话误判为未登录。
            for _ in range(10):
                time.sleep(1.5)
                if _looks_logged_in(page, context):
                    break
        if not _looks_logged_in(page, context):
            if not wait_login:
                print(
                    f"[Pdd{label}] store={store_id} not logged in; skipping for all-store sync",
                    flush=True,
                )
                _close_pw(pw, context)
                return None
            if headless:
                raise RuntimeError(
                    "PDD_NOT_LOGGED_IN: 拼多多未登录（无头模式不弹窗）。"
                    "请先点「打开登录」完成登录后再同步"
                )
            print(f"[Pdd{label}] not logged in; keep window open {_cookie_summary(context)}", flush=True)
            logged_in, page = _wait_until_logged_in(
                page, context, timeout_seconds=300, label=label,
            )
            if not logged_in:
                raise RuntimeError("PDD_NOT_LOGGED_IN: 拼多多商家后台未登录，请打开登录窗口完成登录")
        return pw, context, page
    except Exception:
        _close_pw(pw, context)
        raise


def _is_partial_sync(*, captured: int, platform_total: int, truncated: bool, skipped: int) -> bool:
    """同步是否只完成了部分数据：抓取中断（频控）或存在未登录店铺。"""
    if skipped > 0 or truncated:
        return True
    return bool(platform_total > 0 and captured < platform_total)


def _sync_message(label: str, captured: int, synced: int, skipped: int, platform_total: int) -> str:
    """生成任务 message；数据不完整时说明平台总数与截断原因。"""
    msg = f"已同步{label} {captured} 条（覆盖 {synced} 个店铺）"
    if platform_total > 0 and captured < platform_total:
        msg += f"，平台共 {platform_total} 条，受频控仅部分入库"
    if skipped:
        msg += f"，跳过未登录店铺 {skipped} 个"
    return msg


def run_orders_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    job_id = str(payload.get("job_id") or "")
    # 默认同步近 30 日，从今天往前逐天抓取；需要更长窗口可显式传 date_window=d90
    date_window = str(payload.get("date_window") or "d30").strip() or "d30"

    if not PDD_ORDERS_XHR_READY:
        raise RuntimeError("PDD_ORDERS_NEED_DAY0: 拼多多订单接口尚未完成 Day0 探测固化")

    requested = str(payload.get("store_id") or "").strip()
    all_mode = not requested
    store_ids = _resolve_sync_store_ids(client, tenant_id, requested)

    total = 0
    synced = 0
    skipped = 0
    truncated = False
    platform_total_max = 0
    source_url = ""
    for store_id in store_ids:
        opened = _open_pdd_session(
            client,
            tenant_id,
            store_id,
            wait_login=not all_mode,
            label="orders_sync",
        )
        if opened is None:
            skipped += 1
            continue
        pw, context, page = opened
        try:
            def on_day(day_iso, day_rows, day_url) -> None:
                client.ingest_pdd_orders(
                    {
                        "job_id": job_id,
                        "store_id": store_id,
                        # 统一按近30天窗口标记存储，历史日期同样入库
                        "date_window": "d30",
                        "source_url": str(day_url or ""),
                        "days": [
                            {
                                "replace_day": day_iso,
                                "orders": _sanitize_utf8(day_rows),
                            }
                        ],
                        "partial": False,
                    }
                )

            orders, source_url, meta = fetch_orders_via_xhr(
                page,
                date_window=date_window,
                store_id=store_id,
                on_day=on_day,
            )
        finally:
            _release_pdd_session(pw, context)

        platform_total = int((meta or {}).get("total_hint") or 0)
        store_truncated = bool((meta or {}).get("truncated"))
        if platform_total > platform_total_max:
            platform_total_max = platform_total
        if store_truncated:
            truncated = True
            if int(meta.get("last_page") or 0) > 1:
                _save_pdd_last_page("orders", int(meta["last_page"]))

        # 数据已按天即时入库（on_day），orders 仅用于结果统计。
        total += len(orders)
        synced += 1
        store_partial = _is_partial_sync(
            captured=len(orders),
            platform_total=platform_total,
            truncated=store_truncated,
            skipped=0,
        )

    if all_mode and synced == 0:
        raise RuntimeError("PDD_NOT_LOGGED_IN: 拼多多商家后台未登录，请打开登录窗口完成登录")

    partial = _is_partial_sync(
        captured=total,
        platform_total=platform_total_max,
        truncated=truncated,
        skipped=skipped,
    )
    message = _sync_message("订单", total, synced, skipped, platform_total_max)
    return {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "scope": "orders",
        "orders_count": total,
        "partial": partial,
        "message": message,
        "synced_at": datetime.now(SHANGHAI).isoformat(),
        "source_url": source_url,
        "platform_total": platform_total_max,
    }
def run_products_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    job_id = str(payload.get("job_id") or "")

    if not PDD_PRODUCTS_XHR_READY:
        raise RuntimeError("PDD_PRODUCTS_NEED_DAY0: 拼多多商品接口尚未完成 Day0 探测固化")

    requested = str(payload.get("store_id") or "").strip()
    all_mode = not requested
    store_ids = _resolve_sync_store_ids(client, tenant_id, requested)

    total = 0
    synced = 0
    skipped = 0
    truncated = False
    platform_total_max = 0
    source_url = ""
    for store_id in store_ids:
        opened = _open_pdd_session(
            client,
            tenant_id,
            store_id,
            wait_login=not all_mode,
            label="products_sync",
        )
        if opened is None:
            skipped += 1
            continue
        pw, context, page = opened
        try:
            products, source_url, meta = fetch_products_via_xhr(page, store_id=store_id)
        finally:
            _release_pdd_session(pw, context)

        platform_total = int((meta or {}).get("total_hint") or 0)
        store_truncated = bool((meta or {}).get("truncated"))
        if platform_total > platform_total_max:
            platform_total_max = platform_total
        if store_truncated:
            truncated = True
            if int(meta.get("last_page") or 0) > 1:
                _save_pdd_last_page("products", int(meta["last_page"]))

        products = _sanitize_utf8(products)
        total += len(products)
        synced += 1
        store_partial = _is_partial_sync(
            captured=len(products),
            platform_total=platform_total,
            truncated=store_truncated,
            skipped=0,
        )
        ingest_body = {
            "job_id": job_id,
            "store_id": store_id,
            "source_url": source_url,
            "products": products,
            "partial": store_partial,
            "platform_total": platform_total,
        }
        client.ingest_pdd_products(ingest_body)

    if all_mode and synced == 0:
        raise RuntimeError("PDD_NOT_LOGGED_IN: 拼多多商家后台未登录，请打开登录窗口完成登录")

    partial = _is_partial_sync(
        captured=total,
        platform_total=platform_total_max,
        truncated=truncated,
        skipped=skipped,
    )
    message = _sync_message("商品", total, synced, skipped, platform_total_max)
    return {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "scope": "products",
        "products_count": total,
        "partial": partial,
        "message": message,
        "synced_at": datetime.now(SHANGHAI).isoformat(),
        "source_url": source_url,
        "platform_total": platform_total_max,
    }
def run_compass_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    job_id = str(payload.get("job_id") or "")
    date_type = int(payload.get("date_type") or 1)

    if not PDD_COMPASS_XHR_READY:
        raise RuntimeError("PDD_COMPASS_NEED_DAY0: 拼多多经营罗盘接口尚未完成 Day0 探测固化")

    requested = str(payload.get("store_id") or "").strip()
    all_mode = not requested
    store_ids = _resolve_sync_store_ids(client, tenant_id, requested)

    synced = 0
    skipped = 0
    source_url = ""
    window = "realtime"
    for store_id in store_ids:
        opened = _open_pdd_session(
            client,
            tenant_id,
            store_id,
            wait_login=not all_mode,
            label="compass_sync",
        )
        if opened is None:
            skipped += 1
            continue
        pw, context, page = opened
        try:
            payload_data, source_url = fetch_compass_via_xhr(
                page,
                date_type=date_type,
                store_id=store_id,
            )
        finally:
            _release_pdd_session(pw, context)

        payload_data = _sanitize_utf8(payload_data)
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
        synced += 1

    if all_mode and synced == 0:
        raise RuntimeError("PDD_NOT_LOGGED_IN: 拼多多商家后台未登录，请打开登录窗口完成登录")

    message = f"已同步罗盘（{window}）覆盖 {synced} 个店铺"
    if skipped:
        message += f"，跳过未登录店铺 {skipped} 个"
    return {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "scope": "compass",
        "compass_count": synced,
        "partial": skipped > 0,
        "message": message,
        "synced_at": datetime.now(SHANGHAI).isoformat(),
        "source_url": source_url,
    }
def run_issues_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    job_id = str(payload.get("job_id") or "")

    if not PDD_ISSUES_XHR_READY:
        raise RuntimeError("PDD_ISSUES_NEED_DAY_0: 拼多多问题/售后接口尚未完成 Day0 探测固化")

    requested = str(payload.get("store_id") or "").strip()
    all_mode = not requested
    store_ids = _resolve_sync_store_ids(client, tenant_id, requested)

    total = 0
    synced = 0
    skipped = 0
    truncated = False
    platform_total_max = 0
    source_url = ""
    for store_id in store_ids:
        opened = _open_pdd_session(
            client,
            tenant_id,
            store_id,
            wait_login=not all_mode,
            label="issues_sync",
        )
        if opened is None:
            skipped += 1
            continue
        pw, context, page = opened
        try:
            issues, source_url, meta = fetch_issues_via_xhr(page, store_id=store_id)
        finally:
            _release_pdd_session(pw, context)

        platform_total = int((meta or {}).get("total_hint") or 0)
        store_truncated = bool((meta or {}).get("truncated"))
        if platform_total > platform_total_max:
            platform_total_max = platform_total
        if store_truncated:
            truncated = True
            if int(meta.get("last_page") or 0) > 1:
                _save_pdd_last_page("issues", int(meta["last_page"]))

        issues = _sanitize_utf8(issues)
        total += len(issues)
        synced += 1
        store_partial = _is_partial_sync(
            captured=len(issues),
            platform_total=platform_total,
            truncated=store_truncated,
            skipped=0,
        )
        ingest_body = {
            "job_id": job_id,
            "store_id": store_id,
            "source_url": source_url,
            "issues": issues,
            "partial": store_partial,
            "platform_total": platform_total,
        }
        client.ingest_pdd_issues(ingest_body)

    if all_mode and synced == 0:
        raise RuntimeError("PDD_NOT_LOGGED_IN: 拼多多商家后台未登录，请打开登录窗口完成登录")

    partial = _is_partial_sync(
        captured=total,
        platform_total=platform_total_max,
        truncated=truncated,
        skipped=skipped,
    )
    message = _sync_message("问题/售后", total, synced, skipped, platform_total_max)
    return {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "scope": "issues",
        "issues_count": total,
        "partial": partial,
        "message": message,
        "synced_at": datetime.now(SHANGHAI).isoformat(),
        "source_url": source_url,
        "platform_total": platform_total_max,
    }

