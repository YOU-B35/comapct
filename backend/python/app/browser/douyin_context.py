"""Douyin seller browser helpers: pin fxg home, block foreign tabs (店小蜜等)."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from playwright.sync_api import BrowserContext, Page

DOUYIN_SELLER_HOME = "https://fxg.jinritemai.com/"

_RESTORE_OPEN_URLS = 4
_SESSION_FILE_NAMES = (
    "Current Session",
    "Current Tabs",
    "Last Session",
    "Last Tabs",
)
_DOUYIN_FLOW_HOST_MARKERS = (
    "fxg.jinritemai.com",
    "jinritemai.com",
    "douyin.com",
    "bytedance.com",
)


def is_allowed_douyin_flow_url(url: str) -> bool:
    normalized = (url or "").lower().strip()
    if not normalized:
        return True
    if normalized.startswith(("about:", "chrome:", "devtools:", "data:", "blob:")):
        return True
    return any(marker in normalized for marker in _DOUYIN_FLOW_HOST_MARKERS)


def sanitize_profile_startup_for_douyin(
    profile_dir: Path,
    *,
    home_url: str | None = None,
) -> None:
    target = (home_url or DOUYIN_SELLER_HOME).strip() or DOUYIN_SELLER_HOME
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


def close_foreign_douyin_pages(context: BrowserContext) -> int:
    closed = 0
    for page in list(context.pages):
        if is_allowed_douyin_flow_url(page.url):
            continue
        try:
            print(f"[DouyinBrowser] closed foreign tab: {page.url}", flush=True)
            page.close()
            closed += 1
        except Exception:
            pass
    return closed


def install_douyin_only_tab_guard(context: BrowserContext) -> None:
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
            if is_allowed_douyin_flow_url(url):
                return
            try:
                print(f"[DouyinBrowser] blocking foreign navigation: {url}", flush=True)
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
    close_foreign_douyin_pages(context)


def ensure_douyin_home_page(context: BrowserContext, *, force_navigate: bool = True) -> Page:
    for _ in range(2):
        close_foreign_douyin_pages(context)
        page: Page | None = None
        for candidate in context.pages:
            url = (candidate.url or "").lower()
            if "fxg.jinritemai.com" in url:
                page = candidate
                break
        if page is None:
            page = context.new_page()
            force_navigate = True
        if force_navigate or "fxg.jinritemai.com" not in (page.url or "").lower():
            try:
                page.goto(DOUYIN_SELLER_HOME, wait_until="domcontentloaded", timeout=60_000)
            except Exception:
                try:
                    page.goto(DOUYIN_SELLER_HOME, wait_until="commit", timeout=30_000)
                except Exception:
                    pass
        try:
            page.bring_to_front()
        except Exception:
            pass
        close_foreign_douyin_pages(context)
        if "fxg.jinritemai.com" in (page.url or "").lower():
            return page
        time.sleep(0.35)
    page = context.new_page()
    page.goto(DOUYIN_SELLER_HOME, wait_until="commit", timeout=30_000)
    close_foreign_douyin_pages(context)
    return page
