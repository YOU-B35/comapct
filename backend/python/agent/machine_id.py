"""Stable machine fingerprint for Sync Helper bind enrollment."""
from __future__ import annotations

import hashlib
import platform
import socket
from functools import lru_cache


def _windows_machine_guid() -> str:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            text = str(value or "").strip()
            if text:
                return text
    except Exception:
        pass
    return ""


def _fallback_machine_id() -> str:
    """Non-Windows / registry-missing fallback — still stable per host where possible."""
    parts = [
        platform.node() or "",
        platform.system() or "",
        platform.machine() or "",
        platform.processor() or "",
    ]
    joined = "|".join(p.strip() for p in parts if p and p.strip())
    return joined or "unknown-machine"


@lru_cache(maxsize=1)
def machine_fingerprint() -> str:
    """Stable non-empty fingerprint: sha256(hostname + Windows MachineGuid)."""
    hostname = (socket.gethostname() or platform.node() or "host").strip() or "host"
    guid = _windows_machine_guid()
    if not guid:
        guid = _fallback_machine_id()
    raw = f"{hostname}|{guid}".encode("utf-8", errors="replace")
    digest = hashlib.sha256(raw).hexdigest()
    return digest
