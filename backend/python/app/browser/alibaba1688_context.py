"""1688 Playwright context / profile helpers."""
from __future__ import annotations

import os
from pathlib import Path

from app.session_scope import normalize_session_key, resolve_platform_profile_dir

_LOCK_NAMES = (
    "SingletonLock",
    "SingletonCookie",
    "SingletonSocket",
    "lockfile",
    "LOCK",
)

_PROFILE_ROOT = Path(__file__).resolve().parents[2] / ".1688-browser-profile"


def _profile_root() -> Path:
    override = os.environ.get("A1688_PROFILE_ROOT", "").strip()
    return Path(override) if override else _PROFILE_ROOT


def crawl_headless_enabled() -> bool:
    """Data crawls default headless. Set A1688_HEADED=1 to show a window."""
    return os.getenv("A1688_HEADED", "").strip().lower() not in {"1", "true", "yes"}


def profile_dir(tenant_id: int, store_id: str | None = None) -> Path:
    key = normalize_session_key(store_id)
    root = _profile_root()
    if key == "default":
        # 兼容旧版：default 店铺沿用平铺 tenant-{id}，避免既有登录态失效
        legacy = root / f"tenant-{tenant_id}"
        legacy.mkdir(parents=True, exist_ok=True)
        return legacy
    path = resolve_platform_profile_dir(
        "1688",
        tenant_id,
        key,
        root=root,
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def clear_stale_profile_locks(tenant_id: int, store_id: str | None = None) -> None:
    """Remove Chromium singleton locks left by a crashed Helper so login can relaunch."""
    root = profile_dir(tenant_id, store_id)
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
