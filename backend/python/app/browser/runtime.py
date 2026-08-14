from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Callable, Any

from app.temu.session_scope import normalize_session_key


@dataclass
class BrowserRuntime:
    tenant_id: int
    session_key: str
    headless: bool
    context: Any


_LOCK = RLock()
_RUNTIMES: dict[str, BrowserRuntime] = {}


def runtime_key(tenant_id: int, session_key: str | None = None) -> str:
    return f"{tenant_id}:{normalize_session_key(session_key)}"


def get_or_create_browser_runtime(
    *,
    tenant_id: int,
    headless: bool,
    launcher: Callable[[int, bool], Any],
    is_usable: Callable[[Any], bool] | None = None,
    session_key: str | None = None,
) -> BrowserRuntime:
    key = runtime_key(tenant_id, session_key)
    stale: BrowserRuntime | None = None
    with _LOCK:
        existing = _RUNTIMES.get(key)
        if existing is not None:
            if is_usable is None or is_usable(existing.context):
                return existing
            _RUNTIMES.pop(key, None)
            stale = existing
    if stale is not None:
        try:
            stale.context.close()
        except Exception:
            pass
    with _LOCK:
        existing = _RUNTIMES.get(key)
        if existing is not None:
            if is_usable is None or is_usable(existing.context):
                return existing
            _RUNTIMES.pop(key, None)
            try:
                existing.context.close()
            except Exception:
                pass
        context = launcher(tenant_id, headless)
        runtime = BrowserRuntime(
            tenant_id=tenant_id,
            session_key=normalize_session_key(session_key),
            headless=headless,
            context=context,
        )
        _RUNTIMES[key] = runtime
        return runtime


def peek_browser_runtime(*, tenant_id: int, session_key: str | None = None) -> BrowserRuntime | None:
    """Return in-memory runtime if present (does not launch)."""
    key = runtime_key(tenant_id, session_key)
    with _LOCK:
        return _RUNTIMES.get(key)


def discard_browser_runtime(*, tenant_id: int, session_key: str | None = None) -> BrowserRuntime | None:
    """Remove runtime from the registry without closing Playwright (owner thread closes)."""
    key = runtime_key(tenant_id, session_key)
    with _LOCK:
        return _RUNTIMES.pop(key, None)


def _safe_close_context(context: Any, *, label: str = "runtime.close") -> None:
    try:
        context.close()
    except Exception as exc:  # noqa: BLE001
        text = str(exc).lower()
        if (
            "has been closed" in text
            or "target closed" in text
            or "cannot switch" in text
            or "different thread" in text
        ):
            # Playwright sync API is thread-bound; wrong-thread close must not raise.
            print(f"[TemuBrowser] skip {label}: {exc}", flush=True)
            return
        print(f"[TemuBrowser] {label}: {exc}", flush=True)


def close_browser_runtime(*, tenant_id: int, session_key: str | None = None) -> None:
    key = runtime_key(tenant_id, session_key)
    with _LOCK:
        runtime = _RUNTIMES.pop(key, None)
    if runtime is None:
        return
    _safe_close_context(runtime.context, label="runtime.close")


def reset_browser_runtime_for_tests() -> None:
    with _LOCK:
        runtimes = list(_RUNTIMES.values())
        _RUNTIMES.clear()
    for runtime in runtimes:
        _safe_close_context(runtime.context, label="runtime.reset")
