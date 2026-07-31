"""Aggregate per-seller Temu session payloads for API / ingest."""
from __future__ import annotations

from typing import Any

from app.browser.session_state import session_ready
from app.temu.session_scope import DEFAULT_SESSION_KEY, normalize_session_key


def merge_session_meta(session: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    out = dict(session)
    for key in ("session_key", "platform_account_id", "account", "store_names"):
        if key in meta and meta.get(key) is not None:
            out[key] = meta.get(key)
    return out


def aggregate_tenant_sessions(
    tenant_id: int,
    sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    for item in sessions:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["session_key"] = normalize_session_key(str(row.get("session_key") or DEFAULT_SESSION_KEY))
        row["tenant_id"] = tenant_id
        normalized.append(row)

    ready_count = sum(1 for row in normalized if session_ready(row))
    session_count = len(normalized)
    all_ready = session_count > 0 and ready_count == session_count

    primary = next((row for row in normalized if session_ready(row)), None)
    if primary is None and normalized:
        primary = normalized[0]

    out: dict[str, Any] = {
        "tenant_id": tenant_id,
        "sessions": normalized,
        "session_count": session_count,
        "ready_count": ready_count,
        "ready": all_ready,
    }

    if primary:
        for key in (
            "logged_in",
            "profile_busy",
            "requires_auth",
            "mall_id",
            "mall_count",
            "malls",
            "message",
            "error_hint",
            "url",
            "title",
        ):
            if key in primary:
                out[key] = primary.get(key)
    else:
        out.update(
            {
                "logged_in": False,
                "profile_busy": False,
                "requires_auth": True,
                "mall_id": "",
                "mall_count": 0,
                "malls": [],
                "message": "未检测到 Temu 卖家会话",
            }
        )

    return out


def parse_seller_sessions_payload(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    sessions: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        sessions.append(
            {
                "session_key": normalize_session_key(str(item.get("session_key") or DEFAULT_SESSION_KEY)),
                "platform_account_id": str(item.get("platform_account_id") or "").strip(),
                "account": str(item.get("account") or "").strip(),
                "store_names": list(item.get("store_names") or []),
            }
        )
    return sessions
