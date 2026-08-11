"""Temu shop_ids allowlist helpers for scoped daily / employee crawls."""
from __future__ import annotations

from typing import Any, Iterable


def normalize_shop_id_allowlist(shop_ids: Any) -> frozenset[str] | None:
    """Return None when unrestricted (missing/empty); else a frozenset of shop ids."""
    if shop_ids is None:
        return None
    if isinstance(shop_ids, (str, bytes)):
        text = str(shop_ids).strip()
        return frozenset({text}) if text else None
    if not isinstance(shop_ids, Iterable):
        return None
    out: list[str] = []
    for raw in shop_ids:
        text = str(raw or "").strip()
        if text:
            out.append(text)
    return frozenset(out) if out else None


def shop_id_allowed(shop_id: str | None, allowlist: frozenset[str] | None) -> bool:
    if allowlist is None:
        return True
    return str(shop_id or "").strip() in allowlist


def filter_malls_by_shop_ids(malls: Any, shop_ids: Any) -> list[dict[str, Any]]:
    """Keep malls whose mallId/shop_id is in shop_ids; pass-through when unrestricted."""
    rows = [m for m in (malls or []) if isinstance(m, dict)]
    allow = normalize_shop_id_allowlist(shop_ids)
    if allow is None:
        return list(rows)
    filtered: list[dict[str, Any]] = []
    for mall in rows:
        mid = str(mall.get("mallId") or mall.get("shop_id") or "").strip()
        if mid and mid in allow:
            filtered.append(mall)
    return filtered


def filter_crawl_payload_by_shop_ids(payload: dict[str, Any], shop_ids: Any) -> dict[str, Any]:
    """Filter shops/rows in a crawl payload by shop_ids (no-op when unrestricted)."""
    allow = normalize_shop_id_allowlist(shop_ids)
    if allow is None:
        return payload
    shops = [
        s
        for s in (payload.get("shops") or [])
        if isinstance(s, dict) and str(s.get("shop_id") or "").strip() in allow
    ]
    rows = [
        r
        for r in (payload.get("rows") or [])
        if isinstance(r, dict) and str(r.get("shop_id") or "").strip() in allow
    ]
    out = dict(payload)
    out["shops"] = shops
    out["rows"] = rows
    return out
