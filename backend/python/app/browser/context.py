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
        except Exception as exc:  # noqa: BLE001
            text = str(exc).lower()
            if (
                "has been closed" in text
                or "target closed" in text
                or "cannot switch" in text
                or "different thread" in text
            ):
                print(f"[TemuBrowser] skip context.close: {exc}", flush=True)
            else:
                print(f"[TemuBrowser] context.close: {exc}", flush=True)
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


def _bundled_chromium_ready() -> bool:
    """检测 Playwright 内置 Chromium 是否已安装（脚本/冻结 exe 均适用）。"""
    try:
        import playwright

        candidates = [
            Path(playwright.__file__).resolve().parent / "driver" / "package",
        ]
        # 冻结（PyInstaller onedir）时 playwright.__file__ 指向 PYZ 归档内路径，
        # browsers.json 实际解压在 _internal/playwright/driver/package 下。
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidates.append(Path(meipass) / "playwright" / "driver" / "package")
        manifest = next(
            (c / "browsers.json" for c in candidates if (c / "browsers.json").is_file()),
            None,
        )
        if manifest is None or not manifest.is_file():
            return False
        data = json.loads(manifest.read_text(encoding="utf-8"))
        chromium = next(
            (b for b in data.get("browsers", []) if b.get("name") == "chromium"),
            None,
        )
        revision = str((chromium or {}).get("revision") or "")
        if not revision:
            return False
        override = (os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "").strip()
        if override:
            root = Path(override)
        elif sys.platform.startswith("win"):
            root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ms-playwright"
        elif sys.platform == "darwin":
            root = Path.home() / "Library" / "Caches" / "ms-playwright"
        else:
            root = Path.home() / ".cache" / "ms-playwright"
        return any(
            (root / f"{name}-{revision}").is_dir()
            for name in ("chromium", "chromium_headless_shell")
        )
    except Exception:
        return False

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
    # 默认使用 Playwright 内置 Chromium，不依赖本机浏览器。
    # 显式设置 TEMU_BROWSER_CHANNEL（如 chrome/msedge）时改用系统浏览器；
    # 打包 exe 且内置浏览器缺失时回退本机 Chrome/Edge。
    if BROWSER_CHANNEL:
        kwargs["channel"] = BROWSER_CHANNEL
    elif frozen and not _bundled_chromium_ready():
        chrome = _system_chrome_path()
        if chrome:
            kwargs["executable_path"] = chrome
        else:
            kwargs["channel"] = "chrome"

    if headless:
        kwargs["args"].append("--headless=new")
    return kwargs


def _clear_chrome_profile_locks(profile_dir: Path) -> None:
    for name in (
        "lockfile",
        "SingletonLock",
        "SingletonCookie",
        "SingletonSocket",
        "DevToolsActivePort",
    ):
        try:
            (profile_dir / name).unlink(missing_ok=True)
        except Exception:
            pass


def close_tenant_profile_browsers(
    tenant_id: int,
    *,
    session_key: str | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    """Force-close browser processes that are using this tenant's persistent profile."""
    if not sys.platform.startswith("win"):
        return 0

    from app.temu.session_scope import normalize_session_key

    profile_dir = resolve_profile_dir(tenant_id, session_key)
    profile_text = str(profile_dir.resolve())
    key = normalize_session_key(session_key)
    account_needle = f"account-{key}"
    tenant_needle = f"tenant-{tenant_id}"
    # Match full path OR account folder (Playwright cmdlines vary on slash/quoting).
    script = f"""
$profile = {json.dumps(profile_text)}
$profileBack = $profile.ToLowerInvariant()
$profileSlash = $profileBack.Replace('\\', '/')
$accountNeedle = {json.dumps(account_needle.lower())}
$tenantNeedle = {json.dumps(tenant_needle.lower())}
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
        ($cmd.Contains('.temu-browser-profile') -and $cmd.Contains($tenantNeedle) -and $cmd.Contains($accountNeedle))
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
    killed = 0
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
    _clear_chrome_profile_locks(profile_dir)
    sleeper(1.0 if killed else 0.3)
    return killed


def _launch_persistent_context(
    playwright: Playwright,
    profile_dir: Path,
    launch_kwargs: dict,
    *,
    tenant_id: int,
    session_key: str | None,
    attempts: int = 3,
):
    """Launch persistent Chrome; on SingletonLock clash, kill holders and retry."""
    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        try:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                **launch_kwargs,
            )
            context.add_init_script(STEALTH_INIT_SCRIPT)
            return context
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            text = str(exc).lower()
            busy = any(
                token in text
                for token in (
                    "target page, context or browser has been closed",
                    "singleton",
                    "user data directory",
                    "already in use",
                    "browser has been closed",
                )
            )
            if not busy or attempt + 1 >= attempts:
                break
            print(
                f"[TemuBrowser] launch busy (attempt {attempt + 1}/{attempts}), reclaiming profile…",
                flush=True,
            )
            try:
                close_temu_runtime(tenant_id, session_key=session_key)
            except Exception:
                pass
            close_tenant_profile_browsers(tenant_id, session_key=session_key)
            time.sleep(1.2)
    assert last_error is not None
    raise last_error


@contextmanager
def open_temu_context(
    tenant_id: int,
    *,
    headless: bool | None = None,
    session_key: str | None = None,
    skip_profile_pull: bool | None = None,
) -> Generator[tuple[Playwright, BrowserContext], None, None]:
    from app.browser.profile_sync import profile_pull_enabled, pull_profile_if_needed
    from app.browser.temu_cookie_trust import temu_login_cookies_alive
    from app.temu.profile_migration import maybe_migrate_legacy_temu_profile

    # Prefer local cookies after a successful login; remote pull can overwrite them
    # with a stale/empty bundle and force a fresh login page on crawl.
    if skip_profile_pull is None:
        try:
            skip_profile_pull = temu_login_cookies_alive(tenant_id, session_key) is True
        except Exception:
            skip_profile_pull = False

    if (not skip_profile_pull) and profile_pull_enabled():
        try:
            from agent.java_client import AgentApiClient

            pull_profile_if_needed(
                AgentApiClient(),
                platform="temu",
                tenant_id=tenant_id,
                session_key=session_key,
            )
        except Exception:
            pass
    maybe_migrate_legacy_temu_profile(tenant_id, session_key)
    profile_dir: Path = resolve_profile_dir(tenant_id, session_key)
    profile_dir.mkdir(parents=True, exist_ok=True)
    from app.browser.profile_startup import sanitize_profile_startup_for_temu

    # Always wipe session restore before crawl/login launch (店小秘 tabs live in Sessions/).
    sanitize_profile_startup_for_temu(profile_dir, home_url=TEMU_SELLER_HOME)
    try:
        from agent.handlers import _temu_panel_logging_in

        if _temu_panel_logging_in(session_key):
            raise RuntimeError(
                "Temu 登录窗口仍在使用中。请完成登录后再点击「刷新数据」。"
            )
    except RuntimeError:
        raise
    except Exception:
        pass
    effective_headless = is_headless() if headless is None else headless
    launch_kwargs = _launch_kwargs(effective_headless)
    try:
        close_temu_runtime(tenant_id, session_key=session_key)
    except Exception:
        pass
    close_tenant_profile_browsers(tenant_id, session_key=session_key)
    with sync_playwright() as p:
        context = _launch_persistent_context(
            p,
            profile_dir,
            launch_kwargs,
            tenant_id=tenant_id,
            session_key=session_key,
        )
        install_temu_only_tab_guard(context)
        try:
            yield p, context
        finally:
            try:
                context.close()
            except Exception as exc:  # noqa: BLE001
                text = str(exc).lower()
                if "has been closed" not in text and "target closed" not in text:
                    print(f"[TemuBrowser] open_temu_context close: {exc}", flush=True)


def launch_managed_temu_context(
    tenant_id: int,
    *,
    headless: bool | None = None,
    session_key: str | None = None,
    skip_profile_pull: bool = False,
    force_kill_browsers: bool = True,
) -> ManagedBrowserContext:
    from app.browser.profile_lock import is_profile_locked
    from app.browser.profile_sync import profile_pull_enabled, pull_profile_if_needed
    from app.temu.profile_migration import maybe_migrate_legacy_temu_profile

    if (not skip_profile_pull) and profile_pull_enabled():
        try:
            from agent.java_client import AgentApiClient

            pull_profile_if_needed(
                AgentApiClient(),
                platform="temu",
                tenant_id=tenant_id,
                session_key=session_key,
            )
        except Exception:
            pass
    maybe_migrate_legacy_temu_profile(tenant_id, session_key)
    profile_dir: Path = resolve_profile_dir(tenant_id, session_key)
    profile_dir.mkdir(parents=True, exist_ok=True)
    from app.browser.profile_startup import sanitize_profile_startup_for_temu

    sanitize_profile_startup_for_temu(profile_dir, home_url=TEMU_SELLER_HOME)
    effective_headless = is_headless() if headless is None else headless
    launch_kwargs = _launch_kwargs(effective_headless)
    try:
        close_temu_runtime(tenant_id, session_key=session_key)
    except Exception:
        pass
    # PowerShell process scan is slow (~0.7s+); skip when profile is free (login fast path).
    if force_kill_browsers or is_profile_locked(tenant_id, session_key):
        close_tenant_profile_browsers(tenant_id, session_key=session_key)
    playwright = sync_playwright().start()
    try:
        context = _launch_persistent_context(
            playwright,
            profile_dir,
            launch_kwargs,
            tenant_id=tenant_id,
            session_key=session_key,
        )
        install_temu_only_tab_guard(context)
    except Exception:
        try:
            playwright.stop()
        except Exception:
            pass
        raise
    return ManagedBrowserContext(playwright=playwright, context=context)


def is_runtime_context_usable(context: ManagedBrowserContext | BrowserContext) -> bool:
    if getattr(context, "closed", False):
        return False
    try:
        _ = list(context.pages)
        return True
    except Exception:
        return False


def get_or_create_temu_runtime(
    tenant_id: int,
    *,
    headless: bool | None = None,
    session_key: str | None = None,
    skip_profile_pull: bool = False,
    force_kill_browsers: bool = True,
):
    effective_headless = is_headless() if headless is None else headless
    return browser_runtime.get_or_create_browser_runtime(
        tenant_id=tenant_id,
        headless=effective_headless,
        session_key=session_key,
        launcher=lambda runtime_tenant_id, runtime_headless: launch_managed_temu_context(
            runtime_tenant_id,
            headless=runtime_headless,
            session_key=session_key,
            skip_profile_pull=skip_profile_pull,
            force_kill_browsers=force_kill_browsers,
        ),
        is_usable=is_runtime_context_usable,
    )


def close_temu_runtime(tenant_id: int, session_key: str | None = None) -> None:
    browser_runtime.close_browser_runtime(tenant_id=tenant_id, session_key=session_key)


_TEMU_SELLER_HOST_MARKERS = (
    "agentseller.temu.com",
    "seller.kuajingmaihuo.com",
)

# Tabs allowed during Temu automation (SSO / seller). Everything else (店小秘等) is closed.
_TEMU_FLOW_HOST_MARKERS = (
    "temu.com",
    "temu.cn",
    "kuajingmaihuo.com",
)


def is_temu_seller_url(url: str) -> bool:
    normalized = (url or "").lower()
    return any(marker in normalized for marker in _TEMU_SELLER_HOST_MARKERS)


def is_allowed_temu_flow_url(url: str) -> bool:
    """True for blank/chrome internal pages and Temu/跨境卖货 SSO hosts."""
    normalized = (url or "").lower().strip()
    if not normalized:
        return True
    if normalized.startswith(("about:", "chrome:", "devtools:", "data:", "blob:")):
        return True
    return any(marker in normalized for marker in _TEMU_FLOW_HOST_MARKERS)


def close_non_temu_seller_pages(context: BrowserContext) -> int:
    """Drop restored unrelated tabs (店小秘 / other sites) from the crawl profile."""
    closed = 0
    for page in list(context.pages):
        if is_allowed_temu_flow_url(page.url):
            continue
        try:
            page.close()
            closed += 1
            print(f"[TemuBrowser] closed foreign tab: {page.url}", flush=True)
        except Exception:
            pass
    return closed


def install_temu_only_tab_guard(context: BrowserContext) -> None:
    """Auto-close tabs that navigate off Temu flow (blocks 店小秘 etc.)."""

    def _guard_page(page: Page) -> None:
        def _on_frame_navigated(frame) -> None:
            try:
                if frame != page.main_frame:
                    return
            except Exception:
                return
            url = ""
            try:
                url = page.url or ""
            except Exception:
                return
            if is_allowed_temu_flow_url(url):
                return
            try:
                print(f"[TemuBrowser] blocking foreign navigation: {url}", flush=True)
                page.close()
            except Exception:
                pass

        try:
            page.on("framenavigated", _on_frame_navigated)
        except Exception:
            pass

    try:
        context.on("page", _guard_page)
    except Exception:
        pass
    for existing in list(context.pages):
        _guard_page(existing)
    close_non_temu_seller_pages(context)


def ensure_seller_login_page(context: BrowserContext, *, force_navigate: bool = True) -> Page:
    """Open/focus only Temu seller login path; never leave third-party tabs active."""
    # Session restore can re-create 店小秘 tabs shortly after launch — sweep twice.
    for _ in range(2):
        close_non_temu_seller_pages(context)
        page: Page | None = None
        for candidate in context.pages:
            if is_temu_seller_url(candidate.url):
                page = candidate
                break
        if page is None:
            page = context.new_page()
            force_navigate = True
        if force_navigate or not is_temu_seller_url(page.url):
            try:
                page.goto(TEMU_SELLER_HOME, wait_until="domcontentloaded", timeout=45_000)
            except Exception:
                try:
                    page.goto(TEMU_SELLER_HOME, wait_until="commit", timeout=30_000)
                except Exception:
                    pass
        try:
            page.bring_to_front()
        except Exception:
            pass
        close_non_temu_seller_pages(context)
        if is_temu_seller_url(page.url):
            return page
        time.sleep(0.35)
    # Last resort: dedicated tab
    page = context.new_page()
    page.goto(TEMU_SELLER_HOME, wait_until="commit", timeout=30_000)
    close_non_temu_seller_pages(context)
    try:
        page.bring_to_front()
    except Exception:
        pass
    return page


def get_or_open_seller_page(context: BrowserContext) -> Page:
    # Same policy as login: never leave 店小秘 / blank foreign tabs in front.
    return ensure_seller_login_page(context, force_navigate=True)


def requires_auth(url: str) -> bool:
    normalized = (url or "").lower()
    if "/login" in normalized or "/auth/" in normalized:
        return True
    # CN SSO host: only treat login/passport paths as auth — seller console itself is not.
    if "seller.kuajingmaihuo.com" in normalized:
        return any(
            marker in normalized
            for marker in ("passport", "authenticate", "sso", "/login", "/auth")
        )
    return False


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
        current_url = page.url or ""
        # Do not yank the user off Temu CN SSO / seller hosts mid-login.
        if not is_temu_seller_url(current_url) and "agentseller.temu.com" not in current_url.lower():
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
                from app.browser.session_state import session_ready as _session_ready

                status = describe_session(page)
                on_poll(status)
                # If poll already sees a ready seller session with mall, stop waiting
                # even when resolve_mall_id briefly fails (avoids stuck logging_in).
                if _session_ready(status) and str(status.get("mall_id") or "").strip():
                    return str(status.get("mall_id")).strip()
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
