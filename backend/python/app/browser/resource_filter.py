"""Optional network trimming for headless, read-only crawler pages."""
from __future__ import annotations

import os
from typing import Any


_HEAVY_RESOURCE_TYPES = {"font", "image", "media"}


def heavy_resource_blocking_enabled(*, headless: bool) -> bool:
    if not headless:
        return False
    return os.environ.get("CRAWL_BLOCK_HEAVY_RESOURCES", "0").strip().lower() in {"1", "true", "yes", "on"}


def install_heavy_resource_filter(context: Any, *, headless: bool) -> bool:
    """Block presentation-only resources for background data crawls.

    Scripts, stylesheets and XHR/fetch requests are deliberately left untouched;
    the filter is never applied to headed login or CAPTCHA windows.
    """
    if not heavy_resource_blocking_enabled(headless=headless):
        return False

    def _route(route: Any) -> None:
        if getattr(route.request, "resource_type", "") in _HEAVY_RESOURCE_TYPES:
            route.abort()
        else:
            route.continue_()

    try:
        context.route("**/*", _route)
        return True
    except Exception:
        return False
