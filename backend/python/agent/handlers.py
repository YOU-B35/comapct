"""Agent 任务处理器。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import time
import sys
from typing import Any

from agent.browser_lock_pool import BROWSER_LOCK_POOL, task_browser_keys
from agent.java_client import AgentApiClient
from agent.temu_tasks import (
    crawl_and_ingest,
    discover_competitors,
    open_frontend_login_window,
    open_login_window,
    probe_session,
)
from app.amazon.report_crawler import AmazonLoginRequiredError, crawl_amazon
from app.amazon.write_actions import execute_amazon_write
from app.ziniao.client import ZiniaoClient, ZiniaoConfig

CRAWL_TIMEOUT_SECONDS = 2400
CRAWL_TIMEOUT_MINUTES = CRAWL_TIMEOUT_SECONDS // 60

_TEMU_BROWSER_TASK_TYPES = frozenset(
    {
        "temu_crawl",
        "temu_login_open",
        "temu_frontend_login_open",
        "temu_session_probe",
        "temu_competitor_discover",
    }
)

_DOUYIN_BROWSER_TASK_TYPES = frozenset(
    {
        "douyin_session_probe",
        "douyin_login_open",
        "douyin_sync",
        "douyin_products_sync",
    }
)

_1688_BROWSER_TASK_TYPES = frozenset(
    {
        "1688_session_probe",
        "1688_login_open",
        "1688_products_sync",
        "1688_orders_sync",
        "1688_peer_bestsellers_sync",
        "1688_monitor_crawl",
    }
)

_PDD_BROWSER_TASK_TYPES = frozenset(
    {
        "pdd_session_probe",
        "pdd_login_open",
        "pdd_sync",
        "pdd_products_sync",
        "pdd_issues_sync",
    }
)

_TAOBAO_BROWSER_TASK_TYPES = frozenset(
    {
        "taobao_session_probe",
        "taobao_login_open",
        "taobao_sync",
        "taobao_products_sync",
    }
)


def _clear_panel_logging_in(session_key: str | None) -> None:
    key = str(session_key or "").strip()
    if not key:
        return
    try:
        from agent.tray_app import _state

        with _state.lock:
            _state.logging_in.discard(key)
    except Exception:
        pass


def _temu_panel_logging_in(session_key: str | None = None) -> bool:
    """True while panel /api/login holds the Temu profile for this account."""
    try:
        from agent.tray_app import _state

        with _state.lock:
            if not _state.logging_in:
                return False
            key = str(session_key or "").strip()
            if key:
                return key in _state.logging_in
            return True
    except Exception:
        return False


def _wait_out_panel_logging_in(session_key: str | None, *, timeout_seconds: float = 90.0) -> bool:
    """Wait until panel login flag clears. Returns True if idle, False if still busy."""
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while _temu_panel_logging_in(session_key):
        if time.monotonic() >= deadline:
            return False
        time.sleep(1.5)
    return True


def handle_ziniao_discover(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return

    ziniao = ZiniaoClient(ZiniaoConfig.from_env())
    try:
        ziniao.ensure_webdriver_client(wait_seconds=20)
        stores = ziniao.get_browser_list()
        client.complete_task(task_id, status="success", result={"stores": stores})
    except Exception as exc:
        client.complete_task(
            task_id,
            status="failed",
            error_code="ZINIAO_DISCOVER_FAILED",
            error_message=str(exc),
        )


def handle_amazon_sync(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return

    payload = task.get("payload") or {}
    scope = str(payload.get("scope") or "account_health")
    browser_id = str(payload.get("browser_id") or payload.get("external_shop_id") or "")
    browser_oauth = str(payload.get("browser_oauth") or "")
    store_name = str(payload.get("store_name") or "")
    merchant_id = str(payload.get("merchant_id") or "")
    started = time.time()
    print(
        f"[Agent][Amazon] start task_id={task_id} scope={scope} "
        f"browser_id={browser_id or '-'} oauth={'yes' if bool(browser_oauth) else 'no'} "
        f"store={store_name or '-'} merchant={merchant_id or '-'}",
        file=sys.stderr,
    )

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                crawl_amazon,
                scope=scope,
                browser_id=browser_id,
                browser_oauth=browser_oauth,
                store_name=store_name,
                merchant_id=merchant_id,
            )
            result = future.result(timeout=CRAWL_TIMEOUT_SECONDS)
        elapsed = int((time.time() - started) * 1000)
        summary = result.get("result_summary") if isinstance(result, dict) else {}
        print(
            f"[Agent][Amazon] success task_id={task_id} elapsed_ms={elapsed} "
            f"products={summary.get('products_count', '-') if isinstance(summary, dict) else '-'} "
            f"orders={summary.get('orders_count', '-') if isinstance(summary, dict) else '-'}",
            file=sys.stderr,
        )
        client.complete_task_with_retry(task_id, status="success", result=result)
    except FutureTimeoutError:
        print(
            f"[Agent][Amazon] timeout task_id={task_id} after={CRAWL_TIMEOUT_SECONDS}s",
            file=sys.stderr,
        )
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code="AMAZON_SYNC_TIMEOUT",
            error_message=f"Amazon 爬取超时（超过 {CRAWL_TIMEOUT_MINUTES} 分钟），请稍后重试",
        )
    except AmazonLoginRequiredError as exc:
        print(f"[Agent][Amazon] login-required task_id={task_id}: {exc}", file=sys.stderr)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code="AMAZON_LOGIN_REQUIRED",
            error_message=str(exc),
        )
    except Exception as exc:
        message = str(exc)
        error_code = "AMAZON_SYNC_FAILED"
        if "未登录" in message or "login" in message.lower() or "sign in" in message.lower():
            error_code = "AMAZON_LOGIN_REQUIRED"
        print(
            f"[Agent][Amazon] failed task_id={task_id} code={error_code} msg={message}",
            file=sys.stderr,
        )
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=error_code,
            error_message=message,
        )


def handle_amazon_write(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return

    payload = task.get("payload") or {}
    action = str(payload.get("action") or "")
    browser_id = str(payload.get("browser_id") or payload.get("external_shop_id") or "")
    browser_oauth = str(payload.get("browser_oauth") or "")
    store_name = str(payload.get("store_name") or "")
    item_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
    request = payload.get("request") if isinstance(payload.get("request"), dict) else {}

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                execute_amazon_write,
                action=action,
                browser_id=browser_id,
                browser_oauth=browser_oauth,
                store_name=store_name,
                item_payload=item_payload,
                request=request,
            )
            result = future.result(timeout=300)
        client.complete_task_with_retry(task_id, status="success", result=result)
    except AmazonLoginRequiredError as exc:
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code="AMAZON_LOGIN_REQUIRED",
            error_message=str(exc),
        )
    except Exception as exc:
        message = str(exc)
        error_code = "AMAZON_WRITE_FAILED"
        if "AMAZON_WRITE_DOM_FAILED" in message:
            error_code = "AMAZON_WRITE_DOM_FAILED"
        elif "未登录" in message or "login" in message.lower():
            error_code = "AMAZON_LOGIN_REQUIRED"
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=error_code,
            error_message=message,
        )


def handle_temu_login_open(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    session_key = payload.get("session_key")
    try:
        from agent.temu_tasks import open_login_window, wait_login_session_ready

        login_result = open_login_window(tenant_id, session_key=str(session_key or ""))
        # Playwright sync API is not thread-safe — wait on the same worker thread.
        # Report busy snapshot immediately so the website can leave a stale「未登录」state.
        try:
            client.report_temu_session(
                {
                    "tenant_id": tenant_id,
                    "session_key": str(session_key or ""),
                    "ready": False,
                    "logged_in": False,
                    "requires_auth": True,
                    "profile_busy": True,
                    "mall_id": "",
                    "mall_count": 0,
                    "malls": [],
                    "message": "登录窗口已打开。请在弹出的浏览器中完成登录并选择店铺。",
                }
            )
        except Exception as report_exc:  # noqa: BLE001
            print(f"[TemuLogin] busy snapshot failed: {report_exc}", flush=True)

        session = wait_login_session_ready(
            tenant_id,
            session_key=str(session_key or ""),
            timeout_seconds=600,
            poll_seconds=2.0,
            client=client,
        )
        client.complete_task_with_retry(
            task_id,
            status="success",
            result={"session": session, "login": login_result},
        )
    except Exception as exc:
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code="TEMU_LOGIN_OPEN_FAILED",
            error_message=str(exc),
        )


def handle_temu_frontend_login_open(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    url = str(payload.get("url") or "").strip() or None
    try:
        result = open_frontend_login_window(tenant_id, url)
        client.complete_task_with_retry(task_id, status="success", result=result)
    except Exception as exc:
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code="TEMU_FRONTEND_LOGIN_OPEN_FAILED",
            error_message=str(exc),
        )


def handle_temu_session_probe(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    seller_sessions = payload.get("seller_sessions")
    session_key = payload.get("session_key")
    key = str(session_key).strip() if session_key else None
    try:
        session = probe_session(
            tenant_id,
            seller_sessions=seller_sessions if isinstance(seller_sessions, list) else None,
            session_key=key,
        )
        client.complete_task_with_retry(task_id, status="success", result=session)
    except Exception as exc:
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code="TEMU_SESSION_PROBE_FAILED",
            error_message=str(exc),
        )


def handle_temu_crawl(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    report_time = payload.get("report_time")
    report_day = str(report_time).strip() if report_time else None
    if report_day == "":
        report_day = None
    job_id = str(payload.get("job_id") or "")
    seller_sessions = payload.get("seller_sessions")
    session_key = payload.get("session_key")
    shop_ids = payload.get("shop_ids")
    key = str(session_key).strip() if session_key else None
    try:
        from app.temu.shop_scope import normalize_shop_id_allowlist

        allow = normalize_shop_id_allowlist(shop_ids)
        scoped_shop_ids = list(allow) if allow is not None else None
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                crawl_and_ingest,
                client,
                tenant_id,
                report_day,
                seller_sessions if isinstance(seller_sessions, list) else None,
                key,
                scoped_shop_ids,
            )
            result = future.result(timeout=CRAWL_TIMEOUT_SECONDS)
        if job_id:
            result["job_id"] = job_id
        client.complete_task_with_retry(task_id, status="success", result=result)
    except FutureTimeoutError:
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code="TEMU_CRAWL_TIMEOUT",
            error_message=f"Temu 爬取超时（超过 {CRAWL_TIMEOUT_MINUTES} 分钟），请稍后重试",
        )
    except Exception as exc:
        message = str(exc)
        error_code = "TEMU_CRAWL_FAILED"
        if "未登录" in message or "login" in message.lower():
            error_code = "CRAWL_NOT_LOGGED_IN"
        elif "该区暂无权限" in message or "fully-mgt/sale-manage" in message:
            error_code = "TEMU_REGION_NO_PERMISSION"
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=error_code,
            error_message=message,
        )


def handle_temu_competitor_discover(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    keyword = str(payload.get("keyword") or "fishing tackle")
    region = str(payload.get("region") or "za")
    limit = int(payload.get("limit") or 10)
    try:
        result = discover_competitors(tenant_id, keyword, region, limit)
        client.complete_task_with_retry(task_id, status="success", result=result)
    except Exception as exc:
        message = str(exc)
        error_code = "COMPETITOR_CRAWL_FAILED"
        if message.startswith("COMPETITOR_"):
            error_code = message.split(":", 1)[0].strip()
            if error_code == "COMPETITOR_FRONTEND_LOGIN_REQUIRED":
                error_code = "COMPETITOR_LOGIN_REQUIRED"
        elif "未登录" in message or "login" in message.lower():
            error_code = "COMPETITOR_LOGIN_REQUIRED"
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=error_code,
            error_message=message,
        )


def _douyin_error_code(message: str, default: str) -> str:
    text = message or ""
    for code in (
        "DY_NOT_LOGGED_IN",
        "DY_ORDERS_SOURCE_UNAVAILABLE",
        "DY_PRODUCTS_SOURCE_UNAVAILABLE",
        "DY_COMPASS_RANK_SOURCE_UNAVAILABLE",
        "DY_COMPASS_SOURCE_UNAVAILABLE",
        "DY_OPPORTUNITY_SOURCE_UNAVAILABLE",
        "DY_SHOP_MAPPING_REQUIRED",
        "DY_AGENT_OFFLINE",
        "DY_SYNC_FAILED",
    ):
        if text.startswith(code) or code in text:
            return code
    if "未登录" in text:
        return "DY_NOT_LOGGED_IN"
    if "商品榜" in text or "罗盘商品" in text:
        return "DY_COMPASS_RANK_SOURCE_UNAVAILABLE"
    if "罗盘" in text:
        return "DY_COMPASS_SOURCE_UNAVAILABLE"
    if "商机" in text:
        return "DY_OPPORTUNITY_SOURCE_UNAVAILABLE"
    return default


def handle_douyin_session_probe(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    store_id = str(payload.get("store_id") or "").strip() or None
    try:
        from agent.douyin_tasks import probe_session as douyin_probe_session

        session = douyin_probe_session(tenant_id, store_id)
        client.complete_task_with_retry(task_id, status="success", result=session)
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_douyin_error_code(message, "DY_SYNC_FAILED"),
            error_message=message,
        )


def handle_douyin_login_open(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    store_id = str(payload.get("store_id") or "").strip() or None
    try:
        from agent.douyin_tasks import open_login_window as douyin_open_login_window

        session = douyin_open_login_window(tenant_id, timeout_seconds=600, store_id=store_id)
        client.complete_task_with_retry(task_id, status="success", result={"session": session})
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_douyin_error_code(message, "DY_SYNC_FAILED"),
            error_message=message,
        )


def _a1688_error_code(message: str, default: str = "A1688_LOGIN_FAILED") -> str:
    text = (message or "").lower()
    if "offline" in text or "未在线" in text:
        return "A1688_AGENT_OFFLINE"
    if "login" in text or "登录" in text:
        return "A1688_NOT_LOGGED_IN"
    return default


def handle_1688_session_probe(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    store_id = str(payload.get("store_id") or "").strip() or None
    try:
        from agent.alibaba1688_tasks import probe_session

        session = probe_session(tenant_id, store_id)
        client.complete_task_with_retry(task_id, status="success", result={"session": session})
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_a1688_error_code(message),
            error_message=message,
        )


def handle_1688_login_open(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    store_id = str(payload.get("store_id") or "").strip() or None
    try:
        from agent.alibaba1688_tasks import open_login_window

        session = open_login_window(tenant_id, timeout_seconds=600, store_id=store_id)
        client.complete_task_with_retry(task_id, status="success", result={"session": session})
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_a1688_error_code(message),
            error_message=message,
        )


def handle_1688_monitor_crawl(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    payload = task.get("payload") or {}
    try:
        from app.platforms.alibaba1688_monitor_adapter import Alibaba1688MonitorAdapter

        tenant_id = int(payload.get("tenant_id") or 0)
        target = {
            "target_url": str(payload.get("target_url") or ""),
            "crawl_strategy": str(payload.get("crawl_strategy") or "1688_shop_topn"),
            "config_json": str(payload.get("config_json") or "{}"),
        }
        max_products = max(1, int(payload.get("top_n") or 20))
        result = Alibaba1688MonitorAdapter().crawl_target(
            tenant_id=tenant_id,
            target=target,
            max_products=max_products,
        )
        ingested = client.ingest_1688_monitor(
            {
                "tenant_id": tenant_id,
                "target_id": str(payload.get("target_id") or ""),
                "job_id": str(payload.get("job_id") or ""),
                "snapshot_at": result["snapshot_at"],
                "products": result["products"],
            }
        )
        client.complete_task_with_retry(
            task_id,
            status="success",
            result={
                "snapshot_id": str(ingested.get("snapshot_id") or ""),
                "product_count": int(ingested.get("product_count") or len(result["products"])),
                "signal_count": int(ingested.get("signal_count") or 0),
                "crawled_at": result["snapshot_at"],
            },
        )
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_a1688_error_code(message),
            error_message=message,
        )


def handle_1688_products_sync(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    try:
        from agent.alibaba1688_product_tasks import run_products_sync

        result = run_products_sync(client, task)
        client.complete_task_with_retry(task_id, status="success", result=result)
    except Exception as exc:
        message = str(exc)
        code = "A1688_PRODUCTS_SYNC_FAILED"
        if "A1688_PRODUCTS_NEED_DAY0" in message:
            code = "A1688_PRODUCTS_NEED_DAY0"
        elif "A1688_NOT_LOGGED_IN" in message or "未登录" in message:
            code = "A1688_NOT_LOGGED_IN"
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=code,
            error_message=message,
        )


def handle_1688_orders_sync(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    try:
        from agent.alibaba1688_order_tasks import run_orders_sync

        result = run_orders_sync(client, task)
        client.complete_task_with_retry(task_id, status="success", result=result)
    except Exception as exc:
        message = str(exc)
        code = "A1688_ORDERS_SYNC_FAILED"
        if "A1688_ORDERS_NEED_DAY0" in message:
            code = "A1688_ORDERS_NEED_DAY0"
        elif "A1688_ORDERS_SOURCE_UNAVAILABLE" in message:
            code = "A1688_ORDERS_SOURCE_UNAVAILABLE"
        elif "A1688_NOT_LOGGED_IN" in message or "未登录" in message:
            code = "A1688_NOT_LOGGED_IN"
        elif "timeout" in message.lower() or "超时" in message:
            code = "A1688_SYNC_TIMEOUT"
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=code,
            error_message=message,
        )


def handle_1688_peer_bestsellers_sync(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    try:
        from agent.alibaba1688_peer_tasks import run_peer_bestsellers_sync

        result = run_peer_bestsellers_sync(client, task)
        client.complete_task_with_retry(task_id, status="success", result=result)
    except Exception as exc:
        message = str(exc)
        code = "A1688_ORDERS_SYNC_FAILED"
        if "A1688_NOT_LOGGED_IN" in message or "未登录" in message:
            code = "A1688_NOT_LOGGED_IN"
        elif "timeout" in message.lower() or "超时" in message:
            code = "A1688_SYNC_TIMEOUT"
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=code,
            error_message=message,
        )


def handle_douyin_sync(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    try:
        payload = task.get("payload") or {}
        scope = str(payload.get("scope") or "orders").strip().lower()
        if scope == "compass":
            from agent.douyin_tasks import run_compass_sync

            result = run_compass_sync(client, task)
        elif scope == "opportunity":
            from agent.douyin_tasks import run_opportunity_sync

            result = run_opportunity_sync(client, task)
        elif scope == "compass_product_rank":
            from agent.douyin_compass_rank import run_compass_product_rank_sync

            result = run_compass_product_rank_sync(client, task)
        elif scope == "issues":
            from agent.douyin_tasks import run_issues_sync

            result = run_issues_sync(client, task)
        elif scope == "all":
            from agent.douyin_tasks import run_all_sync

            result = run_all_sync(client, task)
        else:
            from agent.douyin_tasks import run_orders_sync

            result = run_orders_sync(client, task)
        client.complete_task_with_retry(task_id, status="success", result=result)
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_douyin_error_code(message, "DY_SYNC_FAILED"),
            error_message=message,
        )


def handle_douyin_products_sync(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    try:
        from agent.douyin_tasks import run_products_sync

        result = run_products_sync(client, task)
        client.complete_task_with_retry(task_id, status="success", result=result)
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_douyin_error_code(message, "DY_SYNC_FAILED"),
            error_message=message,
        )


def _pdd_error_code(message: str, default: str = "PDD_SYNC_FAILED") -> str:
    text = message or ""
    for code in (
        "PDD_AGENT_OFFLINE",
        "PDD_NOT_LOGGED_IN",
        "PDD_LOGIN_FAILED",
        "PDD_SHOP_MAPPING_REQUIRED",
        "PDD_SYNC_IN_PROGRESS",
        "PDD_SYNC_TIMEOUT",
        "PDD_SYNC_FAILED",
        "PDD_PROFILE_BUSY",
        "PDD_ORDERS_NEED_DAY0",
        "PDD_ORDERS_SOURCE_UNAVAILABLE",
        "PDD_PRODUCTS_NEED_DAY0",
        "PDD_PRODUCTS_SOURCE_UNAVAILABLE",
        "PDD_ISSUES_SOURCE_UNAVAILABLE",
        "PDD_COMPASS_SOURCE_UNAVAILABLE",
    ):
        if text.startswith(code) or code in text:
            return code
    if "未登录" in text or "login" in text.lower():
        return "PDD_NOT_LOGGED_IN"
    if "罗盘" in text:
        return "PDD_COMPASS_SOURCE_UNAVAILABLE"
    if "订单" in text:
        return "PDD_ORDERS_SOURCE_UNAVAILABLE"
    if "商品" in text:
        return "PDD_PRODUCTS_SOURCE_UNAVAILABLE"
    if "问题" in text or "售后" in text:
        return "PDD_ISSUES_SOURCE_UNAVAILABLE"
    if "timeout" in text.lower() or "超时" in text:
        return "PDD_SYNC_TIMEOUT"
    return default


def handle_pdd_session_probe(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    try:
        from agent.pdd_tasks import (
            _resolve_profile_store_id,
            _resolve_store_id,
            probe_session as pdd_probe_session,
        )

        resolved = _resolve_store_id(client, tenant_id, str(payload.get("store_id") or ""))
        profile_store = _resolve_profile_store_id(client, tenant_id, resolved)
        store_id = profile_store or None
        session = pdd_probe_session(tenant_id, store_id)
        client.complete_task_with_retry(task_id, status="success", result={"session": session})
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_pdd_error_code(message, "PDD_SYNC_FAILED"),
            error_message=message,
        )


def handle_pdd_login_open(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    try:
        from agent.pdd_tasks import (
            _resolve_profile_store_id,
            _resolve_store_id,
            open_login_window as pdd_open_login_window,
        )

        resolved = _resolve_store_id(client, tenant_id, str(payload.get("store_id") or ""))
        profile_store = _resolve_profile_store_id(client, tenant_id, resolved)
        store_id = profile_store or None
        session = pdd_open_login_window(tenant_id, timeout_seconds=600, store_id=store_id)
        client.complete_task_with_retry(task_id, status="success", result={"session": session})
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_pdd_error_code(message, "PDD_LOGIN_FAILED"),
            error_message=message,
        )


def handle_pdd_sync(client: AgentApiClient, task: dict[str, Any]) -> None:
    """拼多多同步。scope: orders | products | compass | issues | all（默认 orders）"""
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    try:
        payload = task.get("payload") or {}
        scope = str(payload.get("scope") or "orders").strip().lower()
        if scope == "compass":
            from agent.pdd_tasks import run_compass_sync

            result = run_compass_sync(client, task)
        elif scope == "products":
            from agent.pdd_tasks import run_products_sync

            result = run_products_sync(client, task)
        elif scope == "issues":
            from agent.pdd_tasks import run_issues_sync

            result = run_issues_sync(client, task)
        elif scope == "all":
            from agent.pdd_tasks import (
                run_compass_sync,
                run_issues_sync,
                run_orders_sync,
                run_products_sync,
            )

            result = run_orders_sync(client, task)
            for scope_name, scope_fn in (
                ("products", run_products_sync),
                ("compass", run_compass_sync),
                ("issues", run_issues_sync),
            ):
                try:
                    scope_result = scope_fn(client, task)
                    result[scope_name] = scope_result
                    result["partial"] = bool(result.get("partial")) or bool(scope_result.get("partial"))
                    result["message"] = (
                        f"{result.get('message') or ''}；{scope_result.get('message') or ''}"
                    ).strip("；")
                except Exception as scope_exc:  # noqa: BLE001
                    result["partial"] = True
                    result[scope_name] = None
                    result["message"] = (
                        f"{result.get('message') or ''}；{scope_name} 同步失败: {scope_exc}"
                    ).strip("；")
                result["scope"] = "all"
        else:
            from agent.pdd_tasks import run_orders_sync

            result = run_orders_sync(client, task)
        client.complete_task_with_retry(task_id, status="success", result=result)
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_pdd_error_code(message, "PDD_SYNC_FAILED"),
            error_message=message,
        )


def handle_pdd_issues_sync(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    try:
        from agent.pdd_tasks import run_issues_sync

        result = run_issues_sync(client, task)
        client.complete_task_with_retry(task_id, status="success", result=result)
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_pdd_error_code(message, "PDD_SYNC_FAILED"),
            error_message=message,
        )


def handle_pdd_products_sync(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    try:
        from agent.pdd_tasks import run_products_sync

        result = run_products_sync(client, task)
        client.complete_task_with_retry(task_id, status="success", result=result)
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_pdd_error_code(message, "PDD_SYNC_FAILED"),
            error_message=message,
        )


def _taobao_error_code(message: str, default: str = "TAOBAO_SYNC_FAILED") -> str:
    text = message or ""
    for code in (
        "TAOBAO_AGENT_OFFLINE",
        "TAOBAO_NOT_LOGGED_IN",
        "TAOBAO_LOGIN_FAILED",
        "TAOBAO_SHOP_MAPPING_REQUIRED",
        "TAOBAO_SYNC_IN_PROGRESS",
        "TAOBAO_SYNC_TIMEOUT",
        "TAOBAO_SYNC_FAILED",
        "TAOBAO_PROFILE_BUSY",
        "TAOBAO_ORDERS_NEED_DAY0",
        "TAOBAO_ORDERS_SOURCE_UNAVAILABLE",
        "TAOBAO_PRODUCTS_NEED_DAY0",
        "TAOBAO_PRODUCTS_SOURCE_UNAVAILABLE",
        "TAOBAO_COMPASS_SOURCE_UNAVAILABLE",
    ):
        if text.startswith(code) or code in text:
            return code
    if "未登录" in text or "login" in text.lower():
        return "TAOBAO_NOT_LOGGED_IN"
    if "生意参谋" in text or "罗盘" in text:
        return "TAOBAO_COMPASS_SOURCE_UNAVAILABLE"
    if "订单" in text:
        return "TAOBAO_ORDERS_SOURCE_UNAVAILABLE"
    if "商品" in text:
        return "TAOBAO_PRODUCTS_SOURCE_UNAVAILABLE"
    if "timeout" in text.lower() or "超时" in text:
        return "TAOBAO_SYNC_TIMEOUT"
    return default


def handle_taobao_session_probe(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    store_id = str(payload.get("store_id") or "").strip() or None
    try:
        from agent.taobao_tasks import probe_session as taobao_probe_session

        session = taobao_probe_session(tenant_id, store_id)
        client.complete_task_with_retry(task_id, status="success", result={"session": session})
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_taobao_error_code(message, "TAOBAO_SYNC_FAILED"),
            error_message=message,
        )


def handle_taobao_login_open(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    store_id = str(payload.get("store_id") or "").strip() or None
    try:
        from agent.taobao_tasks import open_login_window as taobao_open_login_window

        session = taobao_open_login_window(tenant_id, timeout_seconds=600, store_id=store_id)
        client.complete_task_with_retry(task_id, status="success", result={"session": session})
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_taobao_error_code(message, "TAOBAO_LOGIN_FAILED"),
            error_message=message,
        )


def handle_taobao_sync(client: AgentApiClient, task: dict[str, Any]) -> None:
    """淘宝订单/生意参谋同步。scope: orders | compass | all（默认 orders）"""
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    try:
        payload = task.get("payload") or {}
        scope = str(payload.get("scope") or "orders").strip().lower()
        if scope == "compass":
            from agent.taobao_tasks import run_compass_sync

            result = run_compass_sync(client, task)
        elif scope == "all":
            from agent.taobao_tasks import run_compass_sync, run_orders_sync

            result = run_orders_sync(client, task)
            try:
                compass_result = run_compass_sync(client, task)
                result["compass"] = compass_result
                result["partial"] = bool(result.get("partial")) or bool(compass_result.get("partial"))
                result["message"] = (
                    f"{result.get('message') or ''}；{compass_result.get('message') or ''}"
                ).strip("；")
                result["scope"] = "all"
            except Exception as compass_exc:  # noqa: BLE001
                result["partial"] = True
                result["compass"] = None
                result["message"] = (
                    f"{result.get('message') or ''}；生意参谋同步失败: {compass_exc}"
                ).strip("；")
                result["scope"] = "all"
        else:
            from agent.taobao_tasks import run_orders_sync

            result = run_orders_sync(client, task)
        client.complete_task_with_retry(task_id, status="success", result=result)
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_taobao_error_code(message, "TAOBAO_SYNC_FAILED"),
            error_message=message,
        )


def handle_taobao_products_sync(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    if not task_id:
        return
    try:
        from agent.taobao_tasks import run_products_sync

        result = run_products_sync(client, task)
        client.complete_task_with_retry(task_id, status="success", result=result)
    except Exception as exc:
        message = str(exc)
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code=_taobao_error_code(message, "TAOBAO_SYNC_FAILED"),
            error_message=message,
        )


def dispatch_task(client: AgentApiClient, task: dict[str, Any]) -> None:
    task_type = str(task.get("task_type") or "")
    if task_type in {"ziniao_discover", "amazon_ziniao_discover"}:
        handle_ziniao_discover(client, task)
        return
    if task_type == "amazon_sync":
        handle_amazon_sync(client, task)
        return
    if task_type == "amazon_write":
        handle_amazon_write(client, task)
        return
    if task_type in _TEMU_BROWSER_TASK_TYPES:
        # Wait for panel login outside the browser lock so we don't stall the queue.
        if task_type in ("temu_crawl", "temu_session_probe"):
            payload = task.get("payload") or {}
            key = str(payload.get("session_key") or "").strip() or None
            if _temu_panel_logging_in(key):
                print(f"[Agent] {task_type} waiting for panel login idle key={key}", flush=True)
                if not _wait_out_panel_logging_in(key, timeout_seconds=120):
                    # Prefer waiting over killing a live login Chrome mid-close.
                    task_id = str(task.get("task_id") or task.get("id") or "")
                    if task_id:
                        client.complete_task_with_retry(
                            task_id,
                            status="failed",
                            error_code="TEMU_PROFILE_BUSY",
                            error_message="Temu 登录窗口仍在使用中，请完成登录后再刷新数据",
                        )
                    return
                # Give login thread a moment to finish context.close / cookie flush.
                time.sleep(2.0)
        with BROWSER_LOCK_POOL.guard("temu", *task_browser_keys("temu", task)):
            if task_type == "temu_crawl":
                handle_temu_crawl(client, task)
            elif task_type == "temu_login_open":
                handle_temu_login_open(client, task)
            elif task_type == "temu_frontend_login_open":
                handle_temu_frontend_login_open(client, task)
            elif task_type == "temu_session_probe":
                handle_temu_session_probe(client, task)
            elif task_type == "temu_competitor_discover":
                handle_temu_competitor_discover(client, task)
        return
    if task_type in _DOUYIN_BROWSER_TASK_TYPES:
        with BROWSER_LOCK_POOL.guard("douyin", *task_browser_keys("douyin", task)):
            if task_type == "douyin_session_probe":
                handle_douyin_session_probe(client, task)
            elif task_type == "douyin_login_open":
                handle_douyin_login_open(client, task)
            elif task_type == "douyin_sync":
                handle_douyin_sync(client, task)
            elif task_type == "douyin_products_sync":
                handle_douyin_products_sync(client, task)
        return
    if task_type in _1688_BROWSER_TASK_TYPES:
        with BROWSER_LOCK_POOL.guard("1688", *task_browser_keys("1688", task)):
            if task_type == "1688_session_probe":
                handle_1688_session_probe(client, task)
            elif task_type == "1688_login_open":
                handle_1688_login_open(client, task)
            elif task_type == "1688_monitor_crawl":
                handle_1688_monitor_crawl(client, task)
            elif task_type == "1688_products_sync":
                handle_1688_products_sync(client, task)
            elif task_type == "1688_orders_sync":
                handle_1688_orders_sync(client, task)
            elif task_type == "1688_peer_bestsellers_sync":
                handle_1688_peer_bestsellers_sync(client, task)
        return
    if task_type in _PDD_BROWSER_TASK_TYPES:
        with BROWSER_LOCK_POOL.guard("pdd", *task_browser_keys("pdd", task)):
            if task_type == "pdd_session_probe":
                handle_pdd_session_probe(client, task)
            elif task_type == "pdd_login_open":
                handle_pdd_login_open(client, task)
            elif task_type == "pdd_sync":
                handle_pdd_sync(client, task)
            elif task_type == "pdd_issues_sync":
                handle_pdd_issues_sync(client, task)
            elif task_type == "pdd_products_sync":
                handle_pdd_products_sync(client, task)
        return
    if task_type in _TAOBAO_BROWSER_TASK_TYPES:
        with BROWSER_LOCK_POOL.guard("taobao", *task_browser_keys("taobao", task)):
            if task_type == "taobao_session_probe":
                handle_taobao_session_probe(client, task)
            elif task_type == "taobao_login_open":
                handle_taobao_login_open(client, task)
            elif task_type == "taobao_sync":
                handle_taobao_sync(client, task)
            elif task_type == "taobao_products_sync":
                handle_taobao_products_sync(client, task)
        return
    task_id = str(task.get("task_id") or "")
    if task_id:
        client.complete_task(
            task_id,
            status="failed",
            error_code="UNSUPPORTED_TASK",
            error_message=f"未支持的任务类型: {task_type}",
        )
