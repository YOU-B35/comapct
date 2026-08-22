"""Pinduoduo (拼多多) seller browser helpers.

复刻 ``douyin_context``：钉死 mms.pinduoduo.com 首页、清理 SingletonLock、
屏蔽非拼多多域的标签页（店小蜜/广告等），保证持久化 Profile 单实例运行。

注：XHR 契约待账号到位 probe 后填入 ``agent/pdd_tasks.py``，本模块仅负责
浏览器 Profile 生命周期，与具体 XHR 无关。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Page

PDD_SELLER_HOME = "https://mms.pinduoduo.com/"

_LOCK_NAMES = (
    "lockfile",
    "SingletonLock",
    "SingletonCookie",
    "SingletonSocket",
    "DevToolsActivePort",
)

_PROFILE_BUSY_TOKENS = (
    "target page, context or browser has been closed",
    "singleton",
    "user data directory",
    "already in use",
    "browser has been closed",
)

_RESTORE_OPEN_URLS = 4
_SESSION_FILE_NAMES = (
    "Current Session",
    "Current Tabs",
    "Last Session",
    "Last Tabs",
)
# 拼多多商家后台相关域名（mms 主后台、商家后台、拼多多主站）
_PDD_FLOW_HOST_MARKERS = (
    "pinduoduo.com",
    "mms.pinduoduo.com",
    "mms.pddglobal.com",
    "pddglobal.com",
    "yangkeduo.com",
)


def is_pdd_profile_busy_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(token in text for token in _PROFILE_BUSY_TOKENS)


def clear_pdd_profile_locks(profile_dir: Path) -> None:
    root = Path(profile_dir)
    for name in _LOCK_NAMES:
        try:
            (root / name).unlink(missing_ok=True)
        except OSError:
            pass
    default_lock = root / "Default" / "LOCK"
    try:
        default_lock.unlink(missing_ok=True)
    except OSError:
        pass


def close_pdd_profile_browsers(
    profile_dir: Path,
    *,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    """Force-close Chrome processes using this Pdd tenant profile, then drop singleton locks."""
    root = Path(profile_dir)
    killed = 0
    if sys.platform.startswith("win"):
        profile_text = str(root.resolve())
        tenant_needle = root.name.lower()
        script = f"""
$profile = {json.dumps(profile_text)}
$profileBack = $profile.ToLowerInvariant()
$profileSlash = $profileBack.Replace('\\', '/')
$tenantNeedle = {json.dumps(tenant_needle)}
$names = @('chrome.exe', 'chromium.exe', 'msedge.exe')
$count = 0
for ($i = 0; $i -lt 8; $i += 1) {{
  $matches = Get-CimInstance Win32_Process |
    Where-Object {{
      $cmd = if ($_.CommandLine) {{ $_.CommandLine.ToLowerInvariant() }} else {{ '' }}
      $cmdSlash = $cmd.Replace('\\', '/')
      $_.Name -in $names -and
      $cmd -and
      (
        $cmd.Contains($profileBack) -or
        $cmdSlash.Contains($profileSlash) -or
        ($cmd.Contains('.pdd-browser-profile') -and $cmd.Contains($tenantNeedle))
      )
    }}
  if (-not $matches) {{ break }}
  foreach ($proc in $matches) {{
    try {{
      Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
      $count += 1
    }} catch {{}}
  }}
  Start-Sleep -Milliseconds 300
}}
Write-Output $count
"""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                timeout=20,
            )
            lines = [ln.strip() for ln in (result.stdout or "").splitlines() if ln.strip()]
            if lines:
                try:
                    killed = int(lines[-1])
                except ValueError:
                    killed = 0
        except Exception:
            killed = 0
    clear_pdd_profile_locks(root)
    sleeper(1.0 if killed else 0.3)
    return killed


def launch_pdd_persistent_context(
    playwright: Any,
    profile_dir: Path,
    launch_kwargs: dict[str, Any],
    *,
    attempts: int = 3,
    launch_fn: Callable[[], Any] | None = None,
    reclaim_fn: Callable[[], int] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
):
    """Launch persistent Chrome; on SingletonLock / closed-browser clash, reclaim profile and retry."""
    last_error: BaseException | None = None
    launcher = launch_fn
    if launcher is None:
        def launcher():
            return playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                **launch_kwargs,
            )

    for attempt in range(max(1, attempts)):
        try:
            return launcher()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if not is_pdd_profile_busy_error(exc) or attempt + 1 >= attempts:
                break
            print(
                f"[PddBrowser] launch busy (attempt {attempt + 1}/{attempts}), reclaiming profile…",
                flush=True,
            )
            if reclaim_fn is not None:
                reclaim_fn()
            else:
                close_pdd_profile_browsers(profile_dir, sleeper=sleeper)
            sleeper(1.2)
    assert last_error is not None
    raise last_error


def is_allowed_pdd_flow_url(url: str) -> bool:
    normalized = (url or "").lower().strip()
    if not normalized:
        return True
    if normalized.startswith(("about:", "chrome:", "devtools:", "data:", "blob:")):
        return True
    return any(marker in normalized for marker in _PDD_FLOW_HOST_MARKERS)


def sanitize_profile_startup_for_pdd(
    profile_dir: Path,
    *,
    home_url: str | None = None,
) -> None:
    target = (home_url or PDD_SELLER_HOME).strip() or PDD_SELLER_HOME
    default_dir = Path(profile_dir) / "Default"
    default_dir.mkdir(parents=True, exist_ok=True)

    for name in _SESSION_FILE_NAMES:
        path = default_dir / name
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass

    sessions_dir = default_dir / "Sessions"
    if sessions_dir.exists():
        try:
            shutil.rmtree(sessions_dir, ignore_errors=True)
        except OSError:
            pass
    try:
        sessions_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    prefs_path = default_dir / "Preferences"
    prefs: dict = {}
    if prefs_path.is_file():
        try:
            prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
            if not isinstance(prefs, dict):
                prefs = {}
        except Exception:
            prefs = {}

    session = prefs.get("session")
    if not isinstance(session, dict):
        session = {}
    session["restore_on_startup"] = _RESTORE_OPEN_URLS
    session["startup_urls"] = [target]
    session["startup_urls_with_timestamps"] = []
    prefs["session"] = session

    profile = prefs.get("profile")
    if not isinstance(profile, dict):
        profile = {}
    profile["exit_type"] = "Normal"
    profile["exited_cleanly"] = True
    prefs["profile"] = profile

    try:
        prefs_path.write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def close_foreign_pdd_pages(context: BrowserContext) -> int:
    closed = 0
    for page in list(context.pages):
        if is_allowed_pdd_flow_url(page.url):
            continue
        try:
            print(f"[PddBrowser] closed foreign tab: {page.url}", flush=True)
            page.close()
            closed += 1
        except Exception:
            pass
    return closed


def install_pdd_only_tab_guard(context: BrowserContext) -> None:
    def _guard_page(page: Page) -> None:
        def _on_nav(frame) -> None:
            try:
                if frame != page.main_frame:
                    return
            except Exception:
                return
            try:
                url = page.url or ""
            except Exception:
                return
            if is_allowed_pdd_flow_url(url):
                return
            try:
                print(f"[PddBrowser] blocking foreign navigation: {url}", flush=True)
                page.close()
            except Exception:
                pass

        try:
            page.on("framenavigated", _on_nav)
        except Exception:
            pass

    try:
        context.on("page", _guard_page)
    except Exception:
        pass
    for existing in list(context.pages):
        _guard_page(existing)
    close_foreign_pdd_pages(context)


def ensure_pdd_home_page(context: BrowserContext, *, force_navigate: bool = True) -> Page:
    for _ in range(2):
        close_foreign_pdd_pages(context)
        page: Page | None = None
        for candidate in context.pages:
            url = (candidate.url or "").lower()
            if "mms.pinduoduo.com" in url or "pinduoduo.com" in url:
                page = candidate
                break
        if page is None:
            page = context.new_page()
            force_navigate = True
        if force_navigate or "pinduoduo.com" not in (page.url or "").lower():
            try:
                page.goto(PDD_SELLER_HOME, wait_until="domcontentloaded", timeout=60_000)
            except Exception:
                try:
                    page.goto(PDD_SELLER_HOME, wait_until="commit", timeout=30_000)
                except Exception:
                    pass
        try:
            page.bring_to_front()
        except Exception:
            pass
        close_foreign_pdd_pages(context)
        if "pinduoduo.com" in (page.url or "").lower():
            return page
        time.sleep(0.35)
    page = context.new_page()
    page.goto(PDD_SELLER_HOME, wait_until="commit", timeout=30_000)
    close_foreign_pdd_pages(context)
    return page
