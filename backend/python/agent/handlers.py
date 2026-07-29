"""Agent 任务处理器。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
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
        client.complete_task_with_retry(task_id, status="success", result=result)
    except FutureTimeoutError:
        client.complete_task_with_retry(
            task_id,
            status="failed",
            error_code="AMAZON_SYNC_TIMEOUT",
            error_message=f"Amazon 爬取超时（超过 {CRAWL_TIMEOUT_MINUTES} 分钟），请稍后重试",
        )
    except AmazonLoginRequiredError as exc:
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
    try:
        login_result = open_login_window(tenant_id)
        # 打开登录窗后不要立刻 live probe：会与有头登录助手争用同一 Profile 导致卡死。
        # 仅读缓存即可；未就绪由前端轮询 session。
        from agent.temu_tasks import _run_json_script

        session = _run_json_script("seller_session_status.py", tenant_id, "--cache-only")
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
    try:
        session = probe_session(tenant_id)
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
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(crawl_and_ingest, client, tenant_id, report_day)
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
