"""Temu Agent 任务执行辅助。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from agent.java_client import AgentApiClient
from app.browser.context import (
    close_temu_runtime,
    close_tenant_profile_browsers,
    get_or_create_temu_runtime,
    get_or_open_seller_page,
)
from app.browser.profile_lock import is_profile_locked, read_profile_lock
from app.browser.session_state import session_ready
from app.config import TEMU_SELLER_HOME

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _subprocess_env(tenant_id: int) -> dict[str, str]:
    env = dict(os.environ)
    env["TENANT_ID"] = str(tenant_id)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _run_json_script(script_name: str, tenant_id: int, *extra: str) -> dict[str, Any]:
    # 打包成 .exe 后 sys.executable 指向自身，不能再 subprocess 跑 .py
    if _is_frozen():
        return _run_inprocess(script_name, tenant_id, *extra)

    script = ROOT / script_name
    command = [PYTHON, str(script), "--tenant-id", str(tenant_id), "--json", *extra]
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        env=_subprocess_env(tenant_id),
    )
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "Temu 脚本执行失败").strip()
        raise RuntimeError(message)
    for line in (proc.stdout or "").splitlines():
        trimmed = line.strip()
        if trimmed.startswith("{"):
            return json.loads(trimmed)
    return {}


def _run_inprocess(script_name: str, tenant_id: int, *extra: str) -> dict[str, Any]:
    os.environ["TENANT_ID"] = str(tenant_id)
    if script_name == "seller_session_status.py":
        from seller_session_status import build_cache_only_payload

        if "--cache-only" in extra:
            return build_cache_only_payload(tenant_id)
        return _probe_session_live(tenant_id)
    if script_name == "seller_login.py":
        return open_login_window(tenant_id)
    raise RuntimeError(f"frozen 模式不支持脚本: {script_name}")


def _probe_session_live(tenant_id: int) -> dict[str, Any]:
    from app.browser.context import describe_session, get_or_open_seller_page, open_temu_context
    from app.browser.profile_lock import is_profile_locked, read_session_cache, write_session_cache
    from app.browser.session_state import build_session_payload
    from seller_session_status import build_cache_only_payload, payload_from_cache, profile_busy_error

    if is_profile_locked(tenant_id):
        cached = read_session_cache(tenant_id, max_age_seconds=1800)
        if cached:
            return payload_from_cache(tenant_id, cached, profile_busy=True)
        return build_cache_only_payload(tenant_id)

    profile_busy = False
    try:
        with open_temu_context(tenant_id, headless=True) as (_, context):
            page = get_or_open_seller_page(context)
            page.wait_for_load_state("domcontentloaded", timeout=60_000)
            page.wait_for_timeout(1500)
            status = describe_session(page)
    except Exception as exc:
        if profile_busy_error(exc):
            profile_busy = True
            cached = read_session_cache(tenant_id, max_age_seconds=1800)
            if cached:
                return payload_from_cache(tenant_id, cached, profile_busy=True)
            status = {
                "url": "",
                "title": "",
                "requires_auth": True,
                "logged_in": False,
                "mall_id": "",
                "mall_count": 0,
                "malls": [],
            }
        else:
            raise

    payload = build_session_payload(tenant_id, status, profile_busy=profile_busy)
    if session_ready(status):
        write_session_cache(tenant_id, payload)
    return payload


def open_login_window(tenant_id: int) -> dict[str, Any]:
    """在当前 agent 线程直接打开 seller 页面，确保后续 discover 复用同线程 runtime。"""
    if is_profile_locked(tenant_id):
        lock = read_profile_lock(tenant_id) or {}
        return {
            "tenant_id": tenant_id,
            "opened": False,
            "already_open": True,
            "engine": "playwright",
            "url": TEMU_SELLER_HOME,
            "lock_role": lock.get("role") or "login_assist",
        }

    close_temu_runtime(tenant_id)
    close_tenant_profile_browsers(tenant_id)
    runtime = get_or_create_temu_runtime(tenant_id, headless=False)
    page = get_or_open_seller_page(runtime.context)
    try:
        page.bring_to_front()
    except Exception:
        pass
    return {
        "tenant_id": tenant_id,
        "opened": True,
        "already_open": False,
        "engine": "playwright",
        "url": TEMU_SELLER_HOME,
    }


def open_frontend_login_window(tenant_id: int, url: str | None = None) -> dict[str, Any]:
    """Open real Chrome for Temu buyer-side login (never Playwright — blank login.html)."""
    from app.browser.manual_chrome import DEFAULT_FRONTEND_URL, open_manual_frontend_chrome

    return open_manual_frontend_chrome(tenant_id, url or DEFAULT_FRONTEND_URL)


def probe_session(tenant_id: int) -> dict[str, Any]:
    cached = _run_json_script("seller_session_status.py", tenant_id, "--cache-only")
    if session_ready(cached):
        return cached
    return _run_json_script("seller_session_status.py", tenant_id)


def discover_competitors(tenant_id: int, keyword: str, region: str, limit: int) -> dict[str, Any]:
    from app.crawler.competitor_discovery import discover_competitor_candidates

    return discover_competitor_candidates(
        tenant_id=tenant_id,
        keyword=keyword,
        region=region,
        limit=limit,
    )


def crawl_and_ingest(client: AgentApiClient, tenant_id: int, report_time: str | None) -> dict[str, Any]:
    from app.crawler.temu_crawler import crawl_temu_sales

    payload = crawl_temu_sales(report_time, use_seed=False, tenant_id=tenant_id)
    ingest_payload = {
        "tenant_id": tenant_id,
        "report_time": payload["report_time"],
        "shops": payload.get("shops") or [],
        "rows": payload.get("rows") or [],
    }
    client.ingest_temu(ingest_payload)
    return {
        "tenant_id": tenant_id,
        "report_time": payload["report_time"],
        "shops": len(payload.get("shops") or []),
        "rows": len(payload.get("rows") or []),
    }
