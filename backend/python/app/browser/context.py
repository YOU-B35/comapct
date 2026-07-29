"""持久化浏览器上下文：保留 Temu 登录态与店铺选择"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generator

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from app.browser import runtime as browser_runtime
from app.browser.stealth import BROWSER_ARGS, IGNORE_DEFAULT_ARGS, STEALTH_INIT_SCRIPT
from app.config import (
    BROWSER_CHANNEL,
    MAX_ACTION_DELAY_MS,
    MIN_ACTION_DELAY_MS,
    MALL_STORAGE_KEY,
    TEMU_LOGIN_POLL_SECONDS,
    TEMU_LOGIN_WAIT_SECONDS,
    TEMU_SELLER_HOME,
    TEMU_USER_INFO_API,
    is_headless,
    resolve_profile_dir,
)


@dataclass
class ManagedBrowserContext:
    playwright: Playwright
    context: BrowserContext
    closed: bool = False

    def __getattr__(self, name: str):
        return getattr(self.context, name)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.context.close()
        finally:
            try:
                self.playwright.stop()
            except Exception:
                pass


def human_pause() -> None:
    delay = random.randint(MIN_ACTION_DELAY_MS, MAX_ACTION_DELAY_MS) / 1000.0
    time.sleep(delay)


def _system_chrome_path() -> str | None:
    """打包 .exe 无 Playwright 自带浏览器，必须用本机 Chrome/Edge。"""
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for path in candidates:
        try:
            if path.is_file():
                return str(path)
        except OSError:
            continue
    return None


def _launch_kwargs(headless: bool) -> dict:
    kwargs: dict = {
        "headless": headless,
        "args": list(BROWSER_ARGS),
        "ignore_default_args": IGNORE_DEFAULT_ARGS,
        "viewport": {"width": 1280, "height": 900},
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    }
    frozen = bool(getattr(sys, "frozen", False))
    chrome = _system_chrome_path()
    # 冻结态必须绑本机浏览器，禁止落到 Playwright 自带 chromium_headless_shell
    if frozen and chrome:
        kwargs["executable_path"] = chrome
    elif BROWSER_CHANNEL:
        kwargs["channel"] = BROWSER_CHANNEL
    elif chrome:
        kwargs["executable_path"] = chrome

    if headless:
        kwargs["args"].append("--headless=new")
    return kwargs


def close_tenant_profile_browsers(
    tenant_id: int,
    *,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    """Force-close browser processes that are using this tenant's persistent profile."""
    if not sys.platform.startswith("win"):
        return 0

    profile_dir = resolve_profile_dir(tenant_id)
    profile_text = str(profile_dir.resolve())
    profile_name = f"tenant-{tenant_id}"
    script = f"""
$profile = {json.dumps(profile_text)}
$profileBack = $profile.ToLowerInvariant()
$profileSlash = $profileBack.Replace('\\', '/')
$profileName = {json.dumps(profile_name)}
$names = @('chrome.exe', 'chromium.exe', 'msedge.exe')
$count = 0
for ($i = 0; $i -lt 5; $i += 1) {{
  $matches = Get-CimInstance Win32_Process |
    Where-Object {{
      $cmd = if ($_.CommandLine) {{ $_.CommandLine.ToLowerInvariant() }} else {{ '' }}
      $cmdSlash = $cmd.Replace('\\', '/')
      $_.Name -in $names -and
      $cmd -and
      (
        $cmd.Contains($profileBack) -or
        $cmdSlash.Contains($profileSlash) -or
        ($cmd.Contains('.temu-browser-profile') -and $cmd.Contains($profileName))
      )
    }}
  if (-not $matches) {{ break }}
  foreach ($proc in $matches) {{
    try {{
      Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
      $count += 1
    }} catch {{}}
  }}
  Start-Sleep -Milliseconds 250
}}
Write-Output $count
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        sleeper(0.8)
        return int((result.stdout or "0").strip().splitlines()[-1])
    except Exception:
        return 0


@contextmanager
def open_temu_context(
    tenant_id: int,
    *,
    headless: bool | None = None,
) -> Generator[tuple[Playwright, BrowserContext], None, None]:
    profile_dir: Path = resolve_profile_dir(tenant_id)
    profile_dir.mkdir(parents=True, exist_ok=True)
    effective_headless = is_headless() if headless is None else headless
    launch_kwargs = _launch_kwargs(effective_headless)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            **launch_kwargs,
        )
        context.add_init_script(STEALTH_INIT_SCRIPT)
        try:
            yield p, context
        finally:
            context.close()


def launch_managed_temu_context(tenant_id: int, *, headless: bool | None = None) -> ManagedBrowserContext:
    profile_dir: Path = resolve_profile_dir(tenant_id)
    profile_dir.mkdir(parents=True, exist_ok=True)
    effective_headless = is_headless() if headless is None else headless
    launch_kwargs = _launch_kwargs(effective_headless)
    playwright = sync_playwright().start()
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        **launch_kwargs,
    )
    context.add_init_script(STEALTH_INIT_SCRIPT)
    return ManagedBrowserContext(playwright=playwright, context=context)


def is_runtime_context_usable(context: ManagedBrowserContext | BrowserContext) -> bool:
    if getattr(context, "closed", False):
        return False
    try:
        _ = list(context.pages)
        return True
    except Exception:
        return False


def get_or_create_temu_runtime(tenant_id: int, *, headless: bool | None = None):
    effective_headless = is_headless() if headless is None else headless
    return browser_runtime.get_or_create_browser_runtime(
        tenant_id=tenant_id,
        headless=effective_headless,
        launcher=lambda runtime_tenant_id, runtime_headless: launch_managed_temu_context(
            runtime_tenant_id,
            headless=runtime_headless,
        ),
        is_usable=is_runtime_context_usable,
    )


def close_temu_runtime(tenant_id: int) -> None:
    browser_runtime.close_browser_runtime(tenant_id=tenant_id)


def get_or_open_seller_page(context: BrowserContext) -> Page:
    for page in context.pages:
        if "agentseller.temu.com" in (page.url or ""):
            return page
    page = context.new_page()
    page.goto(TEMU_SELLER_HOME, wait_until="domcontentloaded", timeout=120_000)
    human_pause()
    return page


def requires_auth(url: str) -> bool:
    normalized = (url or "").lower()
    return (
        "/login" in normalized
        or "/auth/" in normalized
        or "seller.kuajingmaihuo.com" in normalized
    )


def read_mall_id_optional(page: Page) -> str:
    mall_id = page.evaluate(f"() => localStorage.getItem({MALL_STORAGE_KEY!r})")
    mall_id = (mall_id or "").strip()
    if mall_id in ("", "null", "undefined"):
        return ""
    return mall_id


def set_mall_id(page: Page, mall_id: str) -> None:
    page.evaluate(
        f"(id) => localStorage.setItem({MALL_STORAGE_KEY!r}, id)",
        mall_id,
    )


def fetch_mall_list(page: Page) -> list[dict]:
    human_pause()
    response = page.request.post(
        TEMU_USER_INFO_API,
        data="{}",
        headers={
            "Content-Type": "application/json",
            "Origin": "https://agentseller.temu.com",
            "Referer": "https://agentseller.temu.com/",
        },
        timeout=60_000,
    )
    if not response.ok:
        return []
    data = response.json()
    if not data.get("success"):
        return []
    return (data.get("result") or {}).get("mallList") or []


def resolve_mall_id(page: Page) -> str:
    mall_id = read_mall_id_optional(page)
    if mall_id:
        return mall_id

    malls = fetch_mall_list(page)
    if not malls:
        raise RuntimeError(
            "Temu 卖家后台未登录或登录已过期。请点击 CrossHub「打开登录窗口」，"
            "在 Chrome 中完成登录并选择店铺后再同步。"
        )

    if len(malls) == 1:
        mall_id = str(malls[0].get("mallId") or "").strip()
        if mall_id:
            set_mall_id(page, mall_id)
            return mall_id

    names = ", ".join(str(m.get("mallName") or m.get("mallId")) for m in malls[:5])
    raise RuntimeError(
        f"卖家后台有 {len(malls)} 个店铺，请在浏览器左上角手动选择要同步的店铺（{names}）。"
    )


def _login_required_message(tenant_id: int) -> str:
    return (
        "Temu 卖家后台尚未登录。请在已打开的 Chrome 窗口中完成登录，"
        "并在左上角选择要同步的店铺，完成后保持本页继续等待同步。"
    )


def wait_for_login_and_mall(
    page: Page,
    *,
    tenant_id: int,
    timeout_seconds: int = TEMU_LOGIN_WAIT_SECONDS,
    poll_interval_seconds: int = TEMU_LOGIN_POLL_SECONDS,
    sleeper: Callable[[float], None] = time.sleep,
    on_poll: Callable[[dict], None] | None = None,
) -> str:
    deadline = time.monotonic() + max(0, timeout_seconds)
    prompt_shown = False
    last_error = ""

    while True:
        if "agentseller.temu.com" not in (page.url or ""):
            page.goto(TEMU_SELLER_HOME, wait_until="domcontentloaded", timeout=120_000)

        try:
            if not is_headless():
                page.bring_to_front()
        except Exception:
            pass

        try:
            page.wait_for_load_state("domcontentloaded", timeout=10_000)
        except Exception:
            pass

        if not requires_auth(page.url or ""):
            try:
                return resolve_mall_id(page)
            except RuntimeError as exc:
                last_error = str(exc)
        else:
            try:
                malls = fetch_mall_list(page)
                if malls:
                    return resolve_mall_id(page)
            except Exception as exc:
                last_error = str(exc)

        if time.monotonic() >= deadline:
            detail = f" Last status: {last_error}" if last_error else ""
            raise RuntimeError(_login_required_message(tenant_id) + detail)

        if not prompt_shown:
            print(_login_required_message(tenant_id), flush=True)
            prompt_shown = True

        if on_poll is not None:
            try:
                on_poll(describe_session(page))
            except Exception:
                pass

        sleeper(poll_interval_seconds)


def read_mall_id(page: Page) -> str:
    return resolve_mall_id(page)


def ensure_logged_in(page: Page) -> str:
    """打开卖家首页并确认已登录、已选店铺。"""
    if "agentseller.temu.com" not in (page.url or ""):
        page.goto(TEMU_SELLER_HOME, wait_until="domcontentloaded", timeout=120_000)
        human_pause()

    if requires_auth(page.url or ""):
        raise RuntimeError(
            "Temu 卖家后台未登录或登录已过期。请点击 CrossHub「打开登录窗口」，"
            "在 Chrome 中完成登录并选择店铺后再同步。"
        )

    return resolve_mall_id(page)


def describe_session(page: Page) -> dict:
    malls = []
    mall_error = ""
    try:
        malls = fetch_mall_list(page)
    except Exception as exc:
        mall_error = str(exc)

    on_auth = requires_auth(page.url or "")
    mall_id = read_mall_id_optional(page)
    if on_auth:
        mall_id = ""
    logged_in = bool(malls) or (bool(mall_id) and not on_auth)

    return {
        "url": page.url,
        "title": page.title(),
        "requires_auth": on_auth and not malls,
        "logged_in": logged_in,
        "mall_id": mall_id,
        "mall_count": len(malls),
        "malls": [
            {"mallId": m.get("mallId"), "mallName": m.get("mallName")}
            for m in malls[:10]
        ],
        "mall_error": mall_error,
        "ready_hint": logged_in,
    }
