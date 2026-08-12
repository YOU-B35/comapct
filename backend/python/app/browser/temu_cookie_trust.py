"""Trust Temu seller login while Chrome profile cookies are still unexpired."""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import resolve_profile_dir
from app.temu.session_scope import normalize_session_key

# Chrome stores expires_utc as microseconds since 1601-01-01 UTC.
_CHROME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)

# Auth markers observed on agentseller / .temu.com after a successful seller login.
_REQUIRED_COOKIE_NAMES = ("AccessToken", "isLogin")


def _chrome_expiry_to_unix(expires_utc: int) -> float | None:
    if not expires_utc or int(expires_utc) <= 0:
        return None
    try:
        dt = _CHROME_EPOCH + timedelta(microseconds=int(expires_utc))
        return dt.timestamp()
    except Exception:
        return None


def _cookies_db_path(tenant_id: int, session_key: str | None = None) -> Path:
    return resolve_profile_dir(tenant_id, session_key) / "Default" / "Network" / "Cookies"


def _read_login_cookie_rows(db_path: Path) -> list[tuple[str, str, int, int]] | None:
    """Return login cookie rows, or None if the Cookie DB cannot be inspected."""
    if not db_path.is_file():
        return []
    tmp_path = ""
    conn = None
    try:
        # Chrome may lock the live DB; copy first.
        with tempfile.NamedTemporaryFile(prefix="temu-cookies-", suffix=".db", delete=False) as tmp:
            tmp_path = tmp.name
        shutil.copy2(db_path, tmp_path)
        conn = sqlite3.connect(tmp_path)
        rows = conn.execute(
            """
            SELECT host_key, name, expires_utc, has_expires
            FROM cookies
            WHERE name IN (?, ?)
              AND (
                host_key LIKE '%temu.com%'
                OR host_key LIKE '%kuajingmaihuo.com%'
              )
            """,
            _REQUIRED_COOKIE_NAMES,
        ).fetchall()
        return [(row[0], row[1], int(row[2] or 0), int(row[3] or 0)) for row in rows]
    except Exception:
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass


def temu_login_cookies_alive(tenant_id: int, session_key: str | None = None) -> bool | None:
    """
    True when required Temu login cookies exist and are not past expires_utc.
    False when cookies are missing or expired.
    None when the Cookie DB cannot be inspected (e.g. Chrome lock).

    Session cookies (has_expires=0) are treated as alive while present.
    """
    key = normalize_session_key(session_key)
    db_path = _cookies_db_path(tenant_id, key)
    rows = _read_login_cookie_rows(db_path)
    if rows is None:
        return None

    now = time.time()
    found: dict[str, bool] = {name: False for name in _REQUIRED_COOKIE_NAMES}

    for _host, name, expires_utc, has_expires in rows:
        if name not in found:
            continue
        if not has_expires:
            found[name] = True
            continue
        exp_unix = _chrome_expiry_to_unix(expires_utc)
        if exp_unix is None:
            continue
        if exp_unix > now:
            found[name] = True

    return all(found.values())
