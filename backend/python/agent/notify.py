"""Desktop / panel notifications for Helper auth and sync failures."""
from __future__ import annotations

import subprocess
import sys
import threading
from typing import Any

# ── Re-auth error codes & hints ──────────────────────────────────────────────
_REAUTH_CODES: set[str] = {
    "CRAWL_NOT_LOGGED_IN",
    "CRAWL_COOKIE_EXPIRED",
    "CRAWL_SESSION_EXPIRED",
    "CRAWL_LOGIN_REQUIRED",
    "SESSION_EXPIRED",
    "NOT_LOGGED_IN",
    "LOGIN_EXPIRED",
    "LOGIN_REQUIRED",
    "AE_SESSION_EXPIRED",
    "TEMU_SESSION_EXPIRED",
}

_REAUTH_HINTS: list[str] = [
    "未登录",
    "登录已过期",
    "登录过期",
    "cookie 过期",
    "Cookie 过期",
    "session expired",
    "session_expired",
    "not logged in",
    "re-auth",
    "需要重新登录",
    "请重新登录",
    "登录失效",
]


def is_reauth_failure(error_code: str | None, error_message: str | None) -> bool:
    """Return True when the error looks like a login/session expiry."""
    code = (error_code or "").strip().upper()
    if code in _REAUTH_CODES:
        return True
    msg = (error_message or "").strip().lower()
    for hint in _REAUTH_HINTS:
        if hint.lower() in msg:
            return True
    return False


def ops_error_code(item: dict[str, Any]) -> str:
    """Extract the error/failure code from an ops job item."""
    code = (item.get("error_code") or item.get("failure_code") or "").strip()
    return code


def ops_error_message(item: dict[str, Any]) -> str:
    """Extract the error/failure message from an ops job item."""
    msg = (item.get("error_message") or item.get("failure_reason") or "").strip()
    return msg


def build_reauth_notification(*, platform: str = "temu", detail: str = "") -> tuple[str, str]:
    """Build (title, body) for a re-auth (login expired) desktop notification."""
    plat_label = {
        "temu": "Temu",
        "aliexpress": "速卖通",
        "amazon": "Amazon",
    }.get((platform or "temu").lower(), platform or "平台")

    title = f"{plat_label} 登录已过期"
    body_parts: list[str] = []
    if detail:
        body_parts.append(detail)
    body_parts.append("Cookie 无法拉取数据")
    body = "，".join(body_parts)
    body += "。请在 CrossHub Sync Helper 面板点击「打开登录窗口」重新登录。"
    return title, body


def should_notify_ops_item(item: dict[str, Any], seen: set[str]) -> bool:
    """Return True for a *new* failed ops item that hasn't been seen yet."""
    status = str(item.get("status") or "").strip().lower()
    if status != "failed":
        return False
    jid = str(item.get("id") or item.get("job_id") or item.get("task_id") or "").strip()
    key = f"fail:{jid}"
    if key in seen:
        return False
    seen.add(key)
    return True


def build_success_notification(
    *,
    platform: str = "temu",
    shops: int | None = None,
    rows: int | None = None,
) -> tuple[str, str]:
    """Build (title, body) for a successful sync desktop notification."""
    plat_label = {
        "temu": "Temu",
        "aliexpress": "速卖通",
        "amazon": "Amazon",
    }.get((platform or "temu").lower(), platform or "平台")

    title = f"{plat_label} 同步成功"
    parts: list[str] = []
    if shops is not None:
        parts.append(f"店铺 {shops}")
    if rows is not None:
        parts.append(f"行数 {rows}")
    if parts:
        body = "、".join(parts) + " 数据已写入"
    else:
        body = "数据已写入"
    return title, body


def should_notify_success_ops_item(item: dict[str, Any], seen: set[str]) -> bool:
    """Return True for a *new* successful ops item that hasn't been seen yet."""
    status = str(item.get("status") or "").strip().lower()
    if status not in ("success", "partial"):
        return False
    jid = str(item.get("id") or item.get("job_id") or item.get("task_id") or "").strip()
    key = f"ok:{jid}"
    if key in seen:
        return False
    seen.add(key)
    return True


# ── Desktop toast ─────────────────────────────────────────────────────────────
_lock = threading.Lock()
_last_desktop_key: str = ""
_last_desktop_at: float = 0.0


def notify_desktop(title: str, body: str) -> None:
    """Best-effort Windows toast / balloon. Never raises."""
    try:
        _notify_windows(title, body)
    except Exception as exc:
        print(f"[Notify] failed: {exc}", file=sys.stderr)


def notify_reauth(*, platform: str = "temu", detail: str = "") -> None:
    """Convenience: build + send a re-auth notification."""
    title, body = build_reauth_notification(platform=platform, detail=detail)
    notify_desktop_deduped(title, body)


def notify_desktop_deduped(title: str, body: str, *, cooldown_seconds: float = 60.0) -> None:
    """Avoid toast spam when the same failure is polled repeatedly."""
    import time

    key = f"{title}|{body}"
    now = time.time()
    with _lock:
        global _last_desktop_key, _last_desktop_at
        if key == _last_desktop_key and (now - _last_desktop_at) < cooldown_seconds:
            return
        _last_desktop_key = key
        _last_desktop_at = now
    notify_desktop(title, body)


def _notify_windows(title: str, body: str) -> None:
    """Show a Windows balloon notification via PowerShell NotifyIcon."""
    # Escape single quotes for PowerShell
    safe_title = title.replace("'", "''")
    safe_body = body.replace("'", "''")
    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Warning; "
        "$n.Visible = $true; "
        f"$n.BalloonTipTitle = '{safe_title}'; "
        f"$n.BalloonTipText = '{safe_body}'; "
        "$n.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Warning; "
        "$n.ShowBalloonTip(8000); "
        "Start-Sleep -Seconds 9; "
        "$n.Dispose()"
    )
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
        capture_output=True,
        text=True,
        timeout=15,
        creationflags=creationflags,
    )
    if result.returncode != 0:
        print(
            f"[Notify] powershell rc={result.returncode} err={result.stderr.strip()}",
            file=sys.stderr,
        )
