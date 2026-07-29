from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Callable, Any


@dataclass
class BrowserRuntime:
    tenant_id: int
    headless: bool
    context: Any


_LOCK = RLock()
_RUNTIMES: dict[int, BrowserRuntime] = {}


def get_or_create_browser_runtime(
    *,
    tenant_id: int,
    headless: bool,
    launcher: Callable[[int, bool], Any],
    is_usable: Callable[[Any], bool] | None = None,
) -> BrowserRuntime:
    stale: BrowserRuntime | None = None
    with _LOCK:
        existing = _RUNTIMES.get(tenant_id)
        if existing is not None:
            if is_usable is None or is_usable(existing.context):
                return existing
            _RUNTIMES.pop(tenant_id, None)
            stale = existing
    if stale is not None:
        try:
            stale.context.close()
        except Exception:
            pass
    with _LOCK:
        existing = _RUNTIMES.get(tenant_id)
        if existing is not None:
            if is_usable is None or is_usable(existing.context):
                return existing
            _RUNTIMES.pop(tenant_id, None)
            try:
                existing.context.close()
            except Exception:
                pass
        context = launcher(tenant_id, headless)
        runtime = BrowserRuntime(tenant_id=tenant_id, headless=headless, context=context)
        _RUNTIMES[tenant_id] = runtime
        return runtime


def close_browser_runtime(*, tenant_id: int) -> None:
    with _LOCK:
        runtime = _RUNTIMES.pop(tenant_id, None)
    if runtime is None:
        return
    try:
        runtime.context.close()
    except Exception:
        pass


def reset_browser_runtime_for_tests() -> None:
    with _LOCK:
        runtimes = list(_RUNTIMES.values())
        _RUNTIMES.clear()
    for runtime in runtimes:
        try:
            runtime.context.close()
        except Exception:
            pass
