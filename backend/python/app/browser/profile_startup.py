"""Force Temu-seller-only Chrome startup (block session restore of 店小秘 etc.)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.config import TEMU_SELLER_HOME

# Chrome restore_on_startup: 4 = open URLs from startup_urls
_RESTORE_OPEN_URLS = 4

_SESSION_FILE_NAMES = (
    "Current Session",
    "Current Tabs",
    "Last Session",
    "Last Tabs",
)


def sanitize_profile_startup_for_temu(
    profile_dir: Path,
    *,
    home_url: str | None = None,
) -> None:
    """Clear session restore and pin startup to Temu seller home only.

    Persistent profiles often resurrect old ERP tabs (店小秘等). Login/crawl must not.
    """
    target = (home_url or TEMU_SELLER_HOME).strip() or TEMU_SELLER_HOME
    default_dir = Path(profile_dir) / "Default"
    default_dir.mkdir(parents=True, exist_ok=True)

    for name in _SESSION_FILE_NAMES:
        path = default_dir / name
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass

    # Chrome keeps rotating Session_*/Tabs_* under Sessions/; wipe the whole tree.
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

    browser = prefs.get("browser")
    if not isinstance(browser, dict):
        browser = {}
    browser["has_seen_welcome_page"] = True
    prefs["browser"] = browser

    try:
        prefs_path.write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
