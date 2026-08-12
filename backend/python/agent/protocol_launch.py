from __future__ import annotations

import socket
import sys
from pathlib import Path

PROTOCOL_SCHEME = "crosshub-sync-helper"
PROTOCOL_START_PREFIX = f"{PROTOCOL_SCHEME}://start"


def is_protocol_start_argv(argv: list[str] | None = None) -> bool:
    args = list(argv if argv is not None else sys.argv[1:])
    for a in args:
        text = (a or "").strip().strip('"')
        if text == "--protocol-start":
            return True
        low = text.lower()
        if low.startswith(PROTOCOL_START_PREFIX):
            return True
    return False


def ports_already_serving(
    health_port: int = 18765,
    panel_port: int = 18766,
    host: str = "127.0.0.1",
    timeout: float = 0.4,
) -> bool:
    """True if either health or panel TCP port accepts connections."""
    for port in (health_port, panel_port):
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def register_protocol_hkcu(exe_path: str) -> None:
    if sys.platform != "win32":
        return
    import winreg

    exe = str(Path(exe_path).resolve())
    cmd = f'"{exe}" --protocol-start "%1"'
    root = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\crosshub-sync-helper")
    try:
        winreg.SetValueEx(root, None, 0, winreg.REG_SZ, "URL:CrossHub Sync Helper")
        winreg.SetValueEx(root, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(root, r"shell\open\command") as cmd_key:
            winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, cmd)
    finally:
        winreg.CloseKey(root)
