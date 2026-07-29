"""Open real (non-Playwright) Chrome for Temu buyer-side login.

Playwright-controlled pages often render Temu ``login.html`` as a blank page
(Japanese title 「ログイン」). Buyer OAuth / verification must use normal Chrome
with the tenant profile so cookies persist for later Discover / crawl.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.browser.context import close_temu_runtime, close_tenant_profile_browsers
from app.config import resolve_profile_dir

DEFAULT_FRONTEND_URL = "https://www.temu.com/"
DEFAULT_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008


def find_chrome_executable() -> str:
    env_path = os.getenv("CHROME_PATH", "").strip()
    candidates = [env_path] if env_path else []
    candidates.extend(DEFAULT_CHROME_PATHS)
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        candidates.append(str(Path(local) / "Google/Chrome/Application/chrome.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return "chrome"


def open_manual_frontend_chrome(
    tenant_id: int,
    url: str = DEFAULT_FRONTEND_URL,
    *,
    release_playwright: bool = True,
) -> dict[str, Any]:
    """Close Playwright runtime (optional), unlock profile, open real Chrome."""
    target = (url or DEFAULT_FRONTEND_URL).strip() or DEFAULT_FRONTEND_URL
    profile_dir = resolve_profile_dir(tenant_id)
    profile_dir.mkdir(parents=True, exist_ok=True)

    if release_playwright:
        close_temu_runtime(tenant_id)
    close_tenant_profile_browsers(tenant_id)

    command = [
        find_chrome_executable(),
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--new-window",
        target,
    ]
    popen_kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform.startswith("win"):
        popen_kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

    subprocess.Popen(command, **popen_kwargs)
    return {
        "tenant_id": tenant_id,
        "opened": True,
        "engine": "manual_chrome",
        "url": target,
        "profile_dir": str(profile_dir),
        "message": (
            "Opened normal Chrome for Temu buyer-side login. "
            "Complete login/verification, confirm the page is back on www.temu.com "
            "(not about:blank / login.html), close that Chrome window, then retry."
        ),
    }


def frontend_login_required_error(opened: dict[str, Any] | None = None) -> RuntimeError:
    detail = ""
    if opened and opened.get("url"):
        detail = f" Chrome opened at {opened['url']}."
    return RuntimeError(
        "COMPETITOR_LOGIN_REQUIRED: Temu frontend login or verification is required."
        f"{detail} Complete buyer-side login in the opened normal Chrome window, "
        "close that window completely, then retry discover."
    )
