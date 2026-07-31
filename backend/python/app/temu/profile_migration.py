"""Migrate flat tenant Temu profile → account-{session_key} after multi-account split."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from app.config import resolve_profile_root
from app.temu.session_scope import DEFAULT_SESSION_KEY, normalize_session_key

_MIN_COOKIE_BYTES = 8192
_LEGACY_READY_MAX_AGE = 365 * 24 * 3600


def _cookie_size(profile_dir: Path) -> int:
    path = profile_dir / "Default" / "Network" / "Cookies"
    if not path.is_file():
        return 0
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _read_legacy_session_cache(tenant_id: int, *, root: Path) -> dict[str, Any] | None:
    path = root / f"tenant-{tenant_id}" / ".crosshub-session.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _should_migrate(
    *,
    legacy_dir: Path,
    nested_dir: Path,
    legacy_cache: dict[str, Any] | None,
) -> bool:
    if not legacy_cache or not legacy_cache.get("ready"):
        return False
    legacy_cookies = _cookie_size(legacy_dir)
    if legacy_cookies < _MIN_COOKIE_BYTES:
        return False
    nested_cookies = _cookie_size(nested_dir)
    if nested_cookies >= legacy_cookies * 0.8:
        return False
    nested_cache_path = nested_dir / ".crosshub-session.json"
    if nested_cache_path.is_file():
        try:
            nested_cache = json.loads(nested_cache_path.read_text(encoding="utf-8"))
            if nested_cache.get("ready"):
                return False
        except Exception:
            pass
    return True


def maybe_migrate_legacy_temu_profile(tenant_id: int, session_key: str | None = None) -> bool:
    """Copy legacy flat profile into account-{key} when cookies stayed on tenant-{id}/."""
    key = normalize_session_key(session_key)
    if key == DEFAULT_SESSION_KEY:
        return False

    root = resolve_profile_root()
    legacy_dir = root / f"tenant-{tenant_id}"
    nested_dir = root / f"tenant-{tenant_id}" / f"account-{key}"
    if not legacy_dir.is_dir():
        return False

    legacy_cache = _read_legacy_session_cache(tenant_id, root=root)
    if not _should_migrate(legacy_dir=legacy_dir, nested_dir=nested_dir, legacy_cache=legacy_cache):
        return False

    nested_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(legacy_dir, nested_dir, dirs_exist_ok=True)

    cache_path = nested_dir / ".crosshub-session.json"
    body = dict(legacy_cache or {})
    body["tenant_id"] = tenant_id
    body["session_key"] = key
    cache_path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    print(f"[Profile] migrated legacy tenant-{tenant_id} → account-{key}")
    return True
