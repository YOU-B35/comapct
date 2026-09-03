"""Locate an installed Ziniao desktop client on Windows."""
from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

DEFAULT_CLIENT_PATH = Path(r"C:\Program Files\ziniao\ziniao.exe")
_APP_PATHS_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\ziniao.exe"
_UNINSTALL_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
_ZINIAO_BRAND = "\u7d2b\u9e1f"


def _first_existing_executable(candidates: Iterable[Path | str]) -> Path | None:
    for candidate in candidates:
        try:
            path = Path(candidate).expanduser()
        except (TypeError, ValueError):
            continue
        if path.is_file():
            return path
    return None


def _running_ziniao_executables() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "(Get-Process ziniao -ErrorAction SilentlyContinue).Path"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]


def _registry_path(value: Any) -> Path | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.startswith('"'):
        closing_quote = text.find('"', 1)
        if closing_quote > 1:
            text = text[1:closing_quote]
    else:
        text = text.split(",", 1)[0].strip()
    return Path(text)


def _registry_views(winreg: Any) -> tuple[int, ...]:
    views = [0]
    for name in ("KEY_WOW64_64KEY", "KEY_WOW64_32KEY"):
        view = getattr(winreg, name, 0)
        if view not in views:
            views.append(view)
    return tuple(views)


def _read_registry_value(winreg: Any, hive: Any, key_name: str, value_name: str | None, view: int) -> Any | None:
    try:
        with winreg.OpenKey(hive, key_name, 0, winreg.KEY_READ | view) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            return value
    except OSError:
        return None


def _uninstall_ziniao_executables(winreg: Any, hive: Any, view: int) -> list[Path]:
    candidates: list[Path] = []
    try:
        with winreg.OpenKey(hive, _UNINSTALL_KEY, 0, winreg.KEY_READ | view) as root:
            count = winreg.QueryInfoKey(root)[0]
            subkeys = [winreg.EnumKey(root, index) for index in range(count)]
    except OSError:
        return candidates
    for subkey in subkeys:
        key_name = _UNINSTALL_KEY + "\\" + subkey
        display_name = _read_registry_value(winreg, hive, key_name, "DisplayName", view)
        if not isinstance(display_name, str):
            continue
        lowered = display_name.casefold()
        if "ziniao" not in lowered and _ZINIAO_BRAND not in display_name:
            continue
        location = _read_registry_value(winreg, hive, key_name, "InstallLocation", view)
        if isinstance(location, str) and location.strip():
            base = Path(location.strip())
            candidates.extend((base / "ziniao.exe", base / "Ziniao.exe"))
        icon = _registry_path(_read_registry_value(winreg, hive, key_name, "DisplayIcon", view))
        if icon is not None:
            candidates.append(icon)
    return candidates


def _registry_ziniao_executables() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []
    candidates: list[Path] = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in _registry_views(winreg):
            app_path = _registry_path(_read_registry_value(winreg, hive, _APP_PATHS_KEY, None, view))
            if app_path is not None:
                candidates.append(app_path)
            candidates.extend(_uninstall_ziniao_executables(winreg, hive, view))
    return candidates


def _common_ziniao_executables() -> list[Path]:
    candidates = [DEFAULT_CLIENT_PATH]
    for root in (os.getenv("ProgramFiles", ""), os.getenv("ProgramFiles(x86)", ""), os.getenv("LOCALAPPDATA", ""), os.getenv("APPDATA", "")):
        if root:
            base = Path(root)
            candidates.extend((
                base / "ziniao" / "ziniao.exe", base / "Ziniao" / "ziniao.exe",
                base / "Programs" / "ziniao" / "ziniao.exe", base / "Programs" / "Ziniao" / "ziniao.exe",
            ))
    return candidates


def discover_ziniao_client_path(explicit_path: str = "") -> Path:
    configured = explicit_path.strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(f"ZINIAO_CLIENT_PATH points to a missing client executable: {candidate}")
    for candidates in (_running_ziniao_executables(), _registry_ziniao_executables(), _common_ziniao_executables()):
        found = _first_existing_executable(candidates)
        if found is not None:
            return found
    raise FileNotFoundError(
        "Ziniao client was not found after checking running ziniao.exe, Windows registry, and common install directories. "
        "Set ZINIAO_CLIENT_PATH to the full ziniao.exe path."
    )
