"""FastAPI 本地 Web 面板服务。"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from helper_app.accounts import (
    add_account,
    get_account,
    list_accounts,
    remove_account,
    update_account_status,
    update_account_sync,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="CrossHub Sync Helper")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class AddAccountRequest(BaseModel):
    phone: str
    name: str = ""


class SyncResult(BaseModel):
    session_key: str
    success: bool
    message: str = ""
    shops: list[str] = []


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/accounts")
async def api_list_accounts():
    return {"accounts": list_accounts()}


@app.post("/api/accounts")
async def api_add_account(req: AddAccountRequest):
    if not req.phone.strip():
        raise HTTPException(400, "手机号不能为空")
    entry = add_account(req.phone, req.name)
    return {"ok": True, "account": entry}


@app.delete("/api/accounts/{session_key}")
async def api_remove_account(session_key: str):
    ok = remove_account(session_key)
    if not ok:
        raise HTTPException(404, "账户不存在")
    return {"ok": True}


@app.post("/api/accounts/{session_key}/login")
async def api_login(session_key: str):
    acc = get_account(session_key)
    if not acc:
        raise HTTPException(404, "账户不存在")

    def _do_login():
        try:
            from app.config import resolve_profile_dir

            tenant_id = int(
                __import__("os").environ.get("TENANT_ID", "5")
            )
            profile_dir = resolve_profile_dir(tenant_id, session_key)
            profile_dir.mkdir(parents=True, exist_ok=True)

            from app.browser.context import launch_managed_temu_context

            ctx = launch_managed_temu_context(
                tenant_id=tenant_id, session_key=session_key, headless=False
            )
            from app.config import TEMU_SELLER_HOME

            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(TEMU_SELLER_HOME, wait_until="domcontentloaded", timeout=30000)
            update_account_status(session_key, "login_window_open")
        except Exception as exc:
            update_account_status(session_key, "error", error=str(exc))

    threading.Thread(target=_do_login, daemon=True, name=f"login-{session_key}").start()
    return {"ok": True, "message": "登录窗口正在打开"}


@app.post("/api/accounts/{session_key}/sync")
async def api_sync(session_key: str):
    acc = get_account(session_key)
    if not acc:
        raise HTTPException(404, "账户不存在")

    def _do_sync():
        try:
            import os

            tenant_id = int(os.environ.get("TENANT_ID", "5"))
            from app.crawler.temu_crawler import crawl_temu_sales_live

            result = crawl_temu_sales_live(tenant_id=tenant_id, session_key=session_key)
            shops = [s.get("shop_name", "") for s in (result.get("shops") or [])]
            update_account_sync(session_key, shops=shops)
            update_account_status(session_key, "synced")
        except Exception as exc:
            update_account_status(session_key, "sync_error", error=str(exc))

    threading.Thread(target=_do_sync, daemon=True, name=f"sync-{session_key}").start()
    return {"ok": True, "message": "同步任务已启动"}


@app.post("/api/sync-all")
async def api_sync_all():
    accounts = list_accounts()
    started = 0
    for acc in accounts:
        if acc.get("status") in ("synced", "logged_in", "login_window_open", "not_logged_in"):
            key = acc["session_key"]
            threading.Thread(
                target=_sync_one, args=(key,), daemon=True, name=f"sync-{key}"
            ).start()
            started += 1
    return {"ok": True, "started": started}


def _sync_one(session_key: str):
    try:
        import os

        tenant_id = int(os.environ.get("TENANT_ID", "5"))
        from app.crawler.temu_crawler import crawl_temu_sales_live

        result = crawl_temu_sales_live(tenant_id=tenant_id, session_key=session_key)
        shops = [s.get("shop_name", "") for s in (result.get("shops") or [])]
        update_account_sync(session_key, shops=shops)
        update_account_status(session_key, "synced")
    except Exception as exc:
        update_account_status(session_key, "sync_error", error=str(exc))


@app.get("/api/status")
async def api_status():
    from helper_app.scheduler import get_scheduler_status

    return get_scheduler_status()
