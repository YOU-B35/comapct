"""Shared Temu seller session helpers for login assist, status probe, and crawl."""
from __future__ import annotations

from typing import Any


def _has_mall(status: dict[str, Any]) -> bool:
    mall_id = str(status.get("mall_id") or "").strip()
    if mall_id:
        return True
    return int(status.get("mall_count") or 0) > 0


def session_ready(status: dict[str, Any]) -> bool:
    if status.get("ready"):
        return True
    if status.get("requires_auth"):
        return False
    # Having a mall selection (or mall list) implies the seller console is logged in.
    if not _has_mall(status):
        return False
    logged_in = bool(status.get("logged_in") or status.get("ready_hint") or _has_mall(status))
    return logged_in


def _apply_not_ready_message(payload: dict[str, Any], status: dict[str, Any]) -> None:
    logged_in = bool(status.get("logged_in") or status.get("ready_hint"))
    if logged_in and not _has_mall(status):
        payload["message"] = (
            status.get("message")
            or "已登录 Temu 卖家后台，但尚未选择店铺。请在卖家后台左上角选择店铺后，"
            "回到本页点击「我已完成登录」。"
        )
        payload["error_hint"] = "CRAWL_MALL_NOT_SELECTED"
        return
    if bool(status.get("requires_auth")) or not logged_in:
        payload["message"] = (
            status.get("message")
            or "Temu 卖家后台未登录。请点击「打开登录窗口」，在 CrossHub 弹出的浏览器中完成登录。"
        )
        payload["error_hint"] = "CRAWL_NOT_LOGGED_IN"
        return
    payload["message"] = status.get("message") or "Temu 会话未就绪，请完成登录并选择店铺。"
    payload["error_hint"] = "CRAWL_NOT_LOGGED_IN"


def build_session_payload(
    tenant_id: int,
    status: dict[str, Any],
    *,
    profile_busy: bool = False,
) -> dict[str, Any]:
    ready = session_ready(status)
    payload: dict[str, Any] = {
        "tenant_id": tenant_id,
        "ready": ready,
        "requires_auth": bool(status.get("requires_auth")),
        "logged_in": bool(status.get("logged_in") or status.get("ready_hint")),
        "profile_busy": profile_busy,
        "mall_id": status.get("mall_id") or "",
        "mall_count": int(status.get("mall_count") or 0),
        "malls": status.get("malls") or [],
        "url": status.get("url") or "",
        "title": status.get("title") or "",
        "error_hint": "",
    }
    if profile_busy and not ready:
        payload["message"] = (
            "登录窗口已打开。请在 CrossHub 弹出的浏览器中完成登录并选择店铺，"
            "完成后点击「我已完成登录」或继续等待。"
        )
        payload["error_hint"] = "CRAWL_NOT_LOGGED_IN"
    elif not ready:
        _apply_not_ready_message(payload, status)
    else:
        mall_id = str(status.get("mall_id") or "").strip()
        payload["message"] = status.get("message") or "Temu 卖家后台已就绪，可以同步数据。"
        if mall_id:
            payload["error_hint"] = ""
    return payload


def cache_payload_from_status(tenant_id: int, status: dict[str, Any]) -> dict[str, Any]:
    return build_session_payload(tenant_id, status, profile_busy=False)
