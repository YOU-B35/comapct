"""1688 Playwright context / profile helpers."""
from __future__ import annotations

import os
from pathlib import Path

_LOCK_NAMES = (
    "SingletonLock",
    "SingletonCookie",
    "SingletonSocket",
    "lockfile",
    "LOCK",
)


def crawl_headless_enabled() -> bool:
    """Data crawls default headless. Set A1688_HEADED=1 to show a window."""
    return os.getenv("A1688_HEADED", "").strip().lower() not in {"1", "true", "yes"}


def profile_dir(tenant_id: int) -> Path:
    root = Path(__file__).resolve().parents[2] / ".1688-browser-profile"
    path = root / f"tenant-{tenant_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def clear_stale_profile_locks(tenant_id: int) -> None:
    """Remove Chromium singleton locks left by a crashed Helper so login can relaunch."""
    root = profile_dir(tenant_id)
    for name in _LOCK_NAMES:
        path = root / name
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
    default_lock = root / "Default" / "LOCK"
    try:
        if default_lock.exists():
            default_lock.unlink()
    except OSError:
        pass
