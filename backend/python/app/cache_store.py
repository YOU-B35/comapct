"""Small file-backed TTL cache used to avoid repeated platform requests.

Thread-safe, atomic writes, lazy expiry cleanup. Keys are namespace + key
strings; values are any JSON-serializable object.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable


def _now_default() -> float:
    return time.time()


class CacheStore:
    def __init__(
        self,
        path: Path,
        *,
        default_ttl: int = 86400,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.path = Path(path)
        self.default_ttl = max(0, int(default_ttl))
        self._now = now or _now_default
        self._lock = threading.RLock()
        self._data: dict[str, dict[str, dict[str, Any]]] = {}
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
        if isinstance(raw, dict):
            self._data = raw
        else:
            self._data = {}

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=self.path.name + ".",
            suffix=".tmp",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._data, handle, ensure_ascii=False)
            os.replace(tmp_name, self.path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def _prune(self, namespace: str) -> None:
        now = self._now()
        entries = self._data.get(namespace)
        if not isinstance(entries, dict):
            return
        expired = [k for k, item in entries.items() if _expired(item, now)]
        for key in expired:
            entries.pop(key, None)
        if expired and not entries:
            self._data.pop(namespace, None)

    def get(self, namespace: str, key: str) -> Any | None:
        with self._lock:
            self._prune(namespace)
            item = (self._data.get(namespace) or {}).get(key)
            if item is None or _expired(item, self._now()):
                return None
            return item.get("v")

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        ttl = self.default_ttl if ttl_seconds is None else max(0, int(ttl_seconds))
        expires = 0 if ttl == 0 else self._now() + ttl
        with self._lock:
            entries = self._data.setdefault(namespace, {})
            entries[key] = {"v": value, "exp": expires}
            self._persist()

    def invalidate(self, namespace: str, key: str) -> None:
        with self._lock:
            entries = self._data.get(namespace)
            if isinstance(entries, dict):
                entries.pop(key, None)
                if not entries:
                    self._data.pop(namespace, None)
                self._persist()

    def clear_namespace(self, namespace: str) -> None:
        with self._lock:
            if namespace in self._data:
                del self._data[namespace]
                self._persist()


def _expired(item: dict[str, Any], now: float) -> bool:
    expires = item.get("exp")
    return isinstance(expires, (int, float)) and expires > 0 and now > expires
