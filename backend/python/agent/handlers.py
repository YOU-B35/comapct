"""Agent 任务处理器。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import time
import sys
from typing import Any

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
    try:
        session = probe_session(
            tenant_id,
            seller_sessions=seller_sessions if isinstance(seller_sessions, list) else None,
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
                str(session_key).strip() if session_key else None,
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
    if task_type == "temu_crawl":
        handle_temu_crawl(client, task)
        return
    if task_type == "temu_login_open":
        handle_temu_login_open(client, task)
        return
    if task_type == "temu_frontend_login_open":
        handle_temu_frontend_login_open(client, task)
        return
    if task_type == "temu_session_probe":
        handle_temu_session_probe(client, task)
        return
    if task_type == "temu_competitor_discover":
        handle_temu_competitor_discover(client, task)
        return
    task_id = str(task.get("task_id") or "")
    if task_id:
        client.complete_task(
            task_id,
            status="failed",
            error_code="UNSUPPORTED_TASK",
            error_message=f"未支持的任务类型: {task_type}",
        )
