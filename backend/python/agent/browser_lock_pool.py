"""Per-browser lock pool for agent dispatch.

The agent thread pool already controls how many tasks run at once.  We only
need to keep the same tenant/session/store from being worked on by two threads
at the same time, because two crawlers touching the same profile would corrupt
login state.  Distinct accounts, stores and sessions are free to run in parallel.
"""
from __future__ import annotations

from contextlib import contextmanager
from threading import Lock, RLock
import time
from typing import Any, Iterable

from app.observability.task_timing import record_duration


def _clean(value: Any, default: str = "default") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def browser_lock_key(platform: str, *parts: Any) -> str:
    """Build a stable browser-identity key from any task identity fields."""
    cleaned = [_clean(part) for part in parts] or ["default"]
    safe_platform = _clean(platform, "platform")
    return ":".join([safe_platform, *cleaned])


def _first_payload_value(item: dict[str, Any], fields: Iterable[str]) -> str:
    for field in fields:
        value = item.get(field)
        if value:
            return str(value).strip()
    return ""


def _session_browser_parts(item: Any) -> list[str]:
    account = ""
    store = ""
    if isinstance(item, dict):
        account = _first_payload_value(item, ("session_key", "platform_account_id", "account"))
        store = _first_payload_value(item, ("store_id", "shop_id"))
    if not account and not store:
        account = str(item).strip()
    return [part for part in (account, store) if part] or ["default"]


def task_browser_keys(platform: str, task: dict[str, Any]) -> list[str]:
    """Return the browser identities a task should lock before running."""
    payload = dict((task or {}).get("payload") or {})
    tenant_id = payload.get("tenant_id") or 0

    if platform == "temu":
        seller_sessions = payload.get("seller_sessions")
        if isinstance(seller_sessions, list) and seller_sessions:
            keys: list[str] = []
            for session in seller_sessions:
                keys.append(
                    browser_lock_key(
                        "temu",
                        tenant_id,
                        *_session_browser_parts(session),
                    )
                )
            return list(dict.fromkeys(keys))

    if platform == "amazon":
        identity = (
            payload.get("browser_id")
            or payload.get("external_shop_id")
            or payload.get("store_id")
            or payload.get("session_key")
            or payload.get("platform_account_id")
            or payload.get("account")
        )
        return [browser_lock_key(platform, tenant_id, _clean(identity))]

    account = _first_payload_value(
        payload,
        ("session_key", "platform_account_id", "account"),
    )
    store = _first_payload_value(payload, ("store_id", "shop_id"))
    parts = [tenant_id]
    if account:
        parts.append(account)
    if store:
        parts.append(store)
    if len(parts) == 1:
        parts.append("default")
    return [browser_lock_key(platform, *parts)]


class BrowserLockPool:
    """Re-entrant locks keyed by browser identity, without global platform caps."""

    def __init__(self, limits: dict[str, int] | None = None) -> None:
        # `limits` is accepted for backwards compatibility, but a per-platform
        # cap would reintroduce the global serialization we are removing.
        del limits
        self._locks: dict[str, RLock] = {}
        self._locks_guard = Lock()

    def _rlock(self, key: str) -> RLock:
        with self._locks_guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = RLock()
                self._locks[key] = lock
            return lock

    def guard(self, platform: str, *keys: str) -> Any:
        """Context manager which serializes the given browser identity keys."""
        return self._guard_keys(platform, keys)

    def guard_many(self, platform: str, keys: Iterable[str]) -> Any:
        """Context manager which acquires several browser identities at once."""
        return self._guard_keys(platform, keys)

    def _guard_keys(self, platform: str, keys: Iterable[str]) -> Any:
        ordered = sorted(set(str(k) for k in keys))

        @contextmanager
        def _cm():
            acquired: list[RLock] = []
            wait_started = time.perf_counter()
            try:
                for key in ordered:
                    lock = self._rlock(key)
                    lock.acquire()
                    acquired.append(lock)
                record_duration(f"browser_lock_wait.{platform}", time.perf_counter() - wait_started)
            except BaseException:
                for lock in reversed(acquired):
                    lock.release()
                raise
            try:
                yield
            finally:
                for lock in reversed(acquired):
                    lock.release()

        return _cm()


BROWSER_LOCK_POOL = BrowserLockPool()
