"""Persist a local install marker so the website can detect Sync Helper without scanning disks."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def marker_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    return base / "CrossHub" / "SyncHelper" / "installed.json"


def write_install_marker(version: str = "") -> dict[str, Any]:
    path = marker_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "installed": True,
        "version": (version or "").strip(),
        "installed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def read_install_marker() -> dict[str, Any] | None:
    path = marker_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    data["installed"] = bool(data.get("installed", True))
    return data
