"""1688 Playwright context / profile helpers."""
from __future__ import annotations

from pathlib import Path


def profile_dir(tenant_id: int) -> Path:
    root = Path(__file__).resolve().parents[2] / ".1688-browser-profile"
    path = root / f"tenant-{tenant_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path
