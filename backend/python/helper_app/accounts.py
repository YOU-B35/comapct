"""本地 Temu 卖家账户管理（accounts.json CRUD）。"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_ACCOUNTS_FILE = _DATA_DIR / "accounts.json"


def _ensure_data_dir():
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_raw() -> list[dict[str, Any]]:
    if not _ACCOUNTS_FILE.exists():
        return []
    try:
        return json.loads(_ACCOUNTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_raw(data: list[dict[str, Any]]):
    _ensure_data_dir()
    _ACCOUNTS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _build_session_key(phone: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", phone.strip().lower()).strip("_")
    return slug or "default"


def list_accounts() -> list[dict[str, Any]]:
    return _load_raw()


def get_account(session_key: str) -> dict[str, Any] | None:
    for acc in _load_raw():
        if acc.get("session_key") == session_key:
            return acc
    return None


def add_account(phone: str, name: str = "") -> dict[str, Any]:
    accounts = _load_raw()
    session_key = _build_session_key(phone)

    for acc in accounts:
        if acc.get("session_key") == session_key:
            acc["name"] = name or acc.get("name", "")
            acc["phone"] = phone
            _save_raw(accounts)
            return acc

    entry = {
        "phone": phone.strip(),
        "name": name.strip() or phone.strip(),
        "session_key": session_key,
        "status": "not_logged_in",
        "last_sync": None,
        "shops": [],
        "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    accounts.append(entry)
    _save_raw(accounts)
    return entry


def remove_account(session_key: str) -> bool:
    accounts = _load_raw()
    new_list = [a for a in accounts if a.get("session_key") != session_key]
    if len(new_list) == len(accounts):
        return False
    _save_raw(new_list)
    return True


def update_account_status(session_key: str, status: str, **extra):
    accounts = _load_raw()
    for acc in accounts:
        if acc.get("session_key") == session_key:
            acc["status"] = status
            for k, v in extra.items():
                acc[k] = v
            break
    _save_raw(accounts)


def update_account_sync(session_key: str, shops: list[str] | None = None):
    accounts = _load_raw()
    for acc in accounts:
        if acc.get("session_key") == session_key:
            acc["last_sync"] = time.strftime("%Y-%m-%d %H:%M:%S")
            if shops is not None:
                acc["shops"] = shops
            break
    _save_raw(accounts)
