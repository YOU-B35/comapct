"""Temu Agent 任务执行辅助。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from agent.java_client import AgentApiClient
from app.browser import runtime as browser_runtime
from app.browser.context import (
    close_temu_runtime,
    close_tenant_profile_browsers,
    ensure_seller_login_page,
    get_or_create_temu_runtime,
    get_or_open_seller_page,
    is_runtime_context_usable,
)
from app.browser.profile_lock import is_profile_locked, read_profile_lock
from app.browser.session_state import session_ready
from app.config import TEMU_SELLER_HOME
from app.temu.session_aggregate import parse_seller_sessions_payload
from app.temu.session_scope import normalize_session_key

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
        from seller_session_status import build_cache_only_payload, probe_all_sessions, probe_session_live

        if "--seller-sessions-json" in extra:
            idx = extra.index("--seller-sessions-json")
            raw = extra[idx + 1] if idx + 1 < len(extra) else "[]"
            sessions = json.loads(raw)
            return probe_all_sessions(tenant_id, sessions)
        if "--cache-only" in extra:
            session_key = None
            if "--session-key" in extra:
                idx = extra.index("--session-key")
                session_key = extra[idx + 1] if idx + 1 < len(extra) else None
            return build_cache_only_payload(tenant_id, session_key=session_key)
        session_key = None
        if "--session-key" in extra:
            idx = extra.index("--session-key")
            session_key = extra[idx + 1] if idx + 1 < len(extra) else None
        return probe_session_live(tenant_id, session_key=session_key)
    if script_name == "seller_login.py":
        session_key = None
        if "--session-key" in extra:
            idx = extra.index("--session-key")
            session_key = extra[idx + 1] if idx + 1 < len(extra) else None
        return open_login_window(tenant_id, session_key=session_key)
    raise RuntimeError(f"frozen 模式不支持脚本: {script_name}")


def _probe_session_live(tenant_id: int, session_key: str | None = None) -> dict[str, Any]:
    from app.browser.context import describe_session, get_or_open_seller_page, open_temu_context
    from app.browser.profile_lock import (
        SESSION_CACHE_BUSY_MAX_AGE_SECONDS,
        read_session_cache,
        write_session_cache,
    )
    from app.browser.session_state import build_session_payload
    from app.config import is_headless
    from seller_session_status import build_cache_only_payload, payload_from_cache, profile_busy_error

    key = normalize_session_key(session_key)
    if is_profile_locked(tenant_id, key):
        cached = read_session_cache(
            tenant_id,
            max_age_seconds=SESSION_CACHE_BUSY_MAX_AGE_SECONDS,
            session_key=key,
        )
        if cached:
            return payload_from_cache(tenant_id, cached, profile_busy=True, session_key=key)
        return build_cache_only_payload(tenant_id, session_key=key)

    # Align with crawl (default headed). Headless probes often false-negative to /auth.
    profile_busy = False
    try:
        with open_temu_context(tenant_id, headless=is_headless(), session_key=key) as (_, context):
            page = get_or_open_seller_page(context)
            page.wait_for_load_state("domcontentloaded", timeout=60_000)
            page.wait_for_timeout(1500)
            status = describe_session(page)
    except Exception as exc:
        if profile_busy_error(exc):
            profile_busy = True
            cached = read_session_cache(
                tenant_id,
                max_age_seconds=SESSION_CACHE_BUSY_MAX_AGE_SECONDS,
                session_key=key,
            )
            if cached:
                return payload_from_cache(tenant_id, cached, profile_busy=True, session_key=key)
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
    payload["session_key"] = key
    if session_ready(status):
        write_session_cache(tenant_id, payload, session_key=key)
    return payload


def open_login_window(tenant_id: int, session_key: str | None = None) -> dict[str, Any]:
    import time

    from app.browser.profile_startup import sanitize_profile_startup_for_temu
    from app.config import resolve_profile_dir

    key = normalize_session_key(session_key)
    profile_dir = resolve_profile_dir(tenant_id, key)

    # Fast path: reuse live Playwright runtime, but always force Temu seller URL.
    peeked = browser_runtime.peek_browser_runtime(tenant_id=tenant_id, session_key=key)
    if peeked is not None and is_runtime_context_usable(peeked.context):
        page = ensure_seller_login_page(peeked.context, force_navigate=True)
        return {
            "tenant_id": tenant_id,
            "session_key": key,
            "opened": True,
            "already_open": False,
            "reused": True,
            "engine": "playwright",
            "url": page.url or TEMU_SELLER_HOME,
        }

    # Never leave an orphan Chrome (often restored 店小秘 tabs) as "already open".
    # Reclaim profile, wipe session restore, then open Temu seller only.
    try:
        close_temu_runtime(tenant_id, session_key=key)
    except Exception:
        pass
    try:
        close_tenant_profile_browsers(tenant_id, session_key=key)
    except Exception:
        pass
    time.sleep(0.4)
    sanitize_profile_startup_for_temu(profile_dir, home_url=TEMU_SELLER_HOME)

    runtime = get_or_create_temu_runtime(
        tenant_id,
        headless=False,
        session_key=key,
        skip_profile_pull=True,
        force_kill_browsers=True,
    )
    page = ensure_seller_login_page(runtime.context, force_navigate=True)
    return {
        "tenant_id": tenant_id,
        "session_key": key,
        "opened": True,
        "already_open": False,
        "reused": False,
        "engine": "playwright",
        "url": page.url or TEMU_SELLER_HOME,
    }


def wait_login_session_ready(
    tenant_id: int,
    *,
    session_key: str | None = None,
    timeout_seconds: int = 600,
    poll_seconds: float = 5.0,
    client: AgentApiClient | None = None,
) -> dict[str, Any]:
    """Poll the already-open login browser until seller session is ready; persist cache + optional Java push."""
    from app.browser.context import describe_session, wait_for_login_and_mall
    from app.browser.profile_lock import write_session_cache
    from app.browser.session_state import build_session_payload

    key = normalize_session_key(session_key)
    runtime = get_or_create_temu_runtime(
        tenant_id,
        headless=False,
        session_key=key,
        skip_profile_pull=True,
        force_kill_browsers=False,
    )
    # Keep Temu seller tab only; do not force-navigate (would interrupt mid-login).
    page = ensure_seller_login_page(runtime.context, force_navigate=False)
    reported_ready = {"done": False}

    def _on_poll(status: dict[str, Any]) -> None:
        ready_now = session_ready(status)
        # Keep reporting progress so the website leaves「未登录」as soon as possible.
        payload = build_session_payload(tenant_id, status, profile_busy=not ready_now)
        payload["session_key"] = key
        write_session_cache(tenant_id, payload, session_key=key)
        if client is None:
            return
        try:
            client.report_temu_session(payload)
            if ready_now:
                reported_ready["done"] = True
                print(
                    f"[TemuLogin] session ready reported tenant={tenant_id} key={key} "
                    f"mall={payload.get('mall_id')}",
                    flush=True,
                )
        except Exception as exc:  # noqa: BLE001
            print(f"[TemuLogin] report session failed: {exc}", flush=True)

    wait_for_login_and_mall(
        page,
        tenant_id=tenant_id,
        timeout_seconds=int(timeout_seconds),
        poll_interval_seconds=max(1, int(poll_seconds)),
        on_poll=_on_poll,
    )
    try:
        status = describe_session(page)
    except Exception as exc:  # noqa: BLE001
        # Another task may have reclaimed the profile while we were finishing.
        print(f"[TemuLogin] describe after ready failed (using last status): {exc}", flush=True)
        status = {
            "url": "",
            "title": "",
            "requires_auth": False,
            "logged_in": True,
            "mall_id": "",
            "mall_count": 1,
            "malls": [],
            "ready_hint": True,
        }
    payload = build_session_payload(tenant_id, status, profile_busy=False)
    payload["session_key"] = key
    write_session_cache(tenant_id, payload, session_key=key)
    if client is not None:
        try:
            client.report_temu_session(payload)
        except Exception as exc:  # noqa: BLE001
            print(f"[TemuLogin] final report session failed: {exc}", flush=True)

    # Close under the same browser lock as crawl so refresh cannot kill Chrome mid-flush.
    try:
        from agent.handlers import _TEMU_BROWSER_LOCK

        browser_lock = _TEMU_BROWSER_LOCK
    except Exception:
        browser_lock = None

    def _flush_and_close() -> None:
        import time as _time

        from app.browser import runtime as browser_runtime
        from app.browser.temu_cookie_trust import temu_login_cookies_alive

        # 1) Graceful Playwright close on THIS thread so Cookies flush to disk.
        #    Never force-kill first — that is what caused「第一次刷新又要登录」.
        try:
            page.context.close()
        except Exception as exc:  # noqa: BLE001
            print(f"[TemuLogin] page.context.close: {exc}", flush=True)
        try:
            owned = browser_runtime.discard_browser_runtime(
                tenant_id=tenant_id, session_key=key
            )
            if owned is not None and owned.context is not None:
                # ManagedBrowserContext.close also stops Playwright driver.
                try:
                    owned.context.close()
                except Exception as exc:  # noqa: BLE001
                    print(f"[TemuLogin] owned runtime close: {exc}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[TemuLogin] discard runtime: {exc}", flush=True)
        try:
            from app.browser.profile_lock import clear_profile_lock

            clear_profile_lock(tenant_id, session_key=key)
        except Exception:
            pass
        # 2) Soft reclaim leftover OS Chrome only after graceful close.
        try:
            close_tenant_profile_browsers(tenant_id, session_key=key)
        except Exception:
            pass
        # 3) Wait until cookie DB reflects the login before releasing panel busy.
        cookies_ok = False
        for _ in range(12):
            try:
                if temu_login_cookies_alive(tenant_id, key) is True:
                    cookies_ok = True
                    break
            except Exception:
                pass
            _time.sleep(0.5)
        if not cookies_ok:
            print(
                f"[TemuLogin] WARNING cookies not confirmed after close "
                f"tenant={tenant_id} key={key}",
                flush=True,
            )
        else:
            print(
                f"[TemuLogin] cookies confirmed on disk tenant={tenant_id} key={key}",
                flush=True,
            )
        try:
            from agent.tray_app import _state

            with _state.lock:
                _state.logging_in.discard(key)
        except Exception:
            pass

    if browser_lock is not None:
        with browser_lock:
            _flush_and_close()
    else:
        _flush_and_close()
    # Push outside the browser lock — packing/HTTP must not block crawl.
    try:
        from app.browser.profile_sync import push_profile_sync
        from agent.java_client import AgentApiClient

        push_client = client if client is not None else AgentApiClient()
        push_profile_sync(
            push_client,
            platform="temu",
            tenant_id=tenant_id,
            session_key=key,
            platform_account_id=str(payload.get("platform_account_id") or ""),
            account=str(payload.get("account") or key),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[TemuLogin] profile push after login: {exc}", flush=True)
    print(
        f"[TemuLogin] session ready — cookies flushed to profile "
        f"tenant={tenant_id} key={key}",
        flush=True,
    )
    return payload


def open_frontend_login_window(tenant_id: int, url: str | None = None) -> dict[str, Any]:
    from app.browser.manual_chrome import DEFAULT_FRONTEND_URL, open_manual_frontend_chrome

    return open_manual_frontend_chrome(tenant_id, url or DEFAULT_FRONTEND_URL)


def _sessions_json_arg(seller_sessions: list[dict] | None) -> list[str]:
    if not seller_sessions:
        return []
    return ["--seller-sessions-json", json.dumps(seller_sessions, ensure_ascii=False)]


def probe_session(
    tenant_id: int,
    seller_sessions: list[dict] | None = None,
    session_key: str | None = None,
) -> dict[str, Any]:
    if seller_sessions:
        return _run_json_script(
            "seller_session_status.py",
            tenant_id,
            *_sessions_json_arg(seller_sessions),
        )
    key = normalize_session_key(session_key)
    cached = _run_json_script(
        "seller_session_status.py",
        tenant_id,
        "--cache-only",
        "--session-key",
        key,
    )
    if session_ready(cached):
        return cached
    return _run_json_script(
        "seller_session_status.py",
        tenant_id,
        "--session-key",
        key,
    )


def discover_competitors(tenant_id: int, keyword: str, region: str, limit: int) -> dict[str, Any]:
    import threading

    from app.crawler.competitor_discovery import discover_competitor_candidates

    box: dict[str, Any] = {}
    errors: list[BaseException] = []

    def _run() -> None:
        try:
            close_temu_runtime(tenant_id)
            box["value"] = discover_competitor_candidates(
                tenant_id=tenant_id,
                keyword=keyword,
                region=region,
                limit=limit,
            )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    worker = threading.Thread(
        target=_run,
        name=f"temu-discover-{tenant_id}",
        daemon=True,
    )
    worker.start()
    worker.join(timeout=300)
    if worker.is_alive():
        raise TimeoutError("Temu competitor discover timed out after 300s")
    if errors:
        raise errors[0]
    return box["value"]


def crawl_and_ingest(
    client: AgentApiClient,
    tenant_id: int,
    report_time: str | None,
    seller_sessions: list[dict] | None = None,
    session_key: str | None = None,
    shop_ids: list | None = None,
) -> dict[str, Any]:
    from app.crawler.temu_crawler import crawl_temu_sales
    from app.temu.shop_scope import filter_crawl_payload_by_shop_ids, normalize_shop_id_allowlist

    sessions = parse_seller_sessions_payload(seller_sessions)
    allow = normalize_shop_id_allowlist(shop_ids)
    scoped_ids = list(allow) if allow is not None else None
    payload = crawl_temu_sales(
        report_time,
        use_seed=False,
        tenant_id=tenant_id,
        session_key=session_key,
        seller_sessions=sessions or None,
        shop_ids=scoped_ids,
    )
    payload = filter_crawl_payload_by_shop_ids(payload, scoped_ids)
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
        "sessions_synced": payload.get("sessions_synced"),
        "session_errors": payload.get("session_errors") or [],
    }
