"""1688 shop collector: bestseller list + offer details via the logged-in session."""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Any

from app.cache_store import CacheStore
from app.platforms.alibaba1688_monitor_parse import (
    parse_offer_detail_responses,
    parse_shop_list_response,
    parse_shopcard_response,
)
from app.platforms.alibaba1688_monitor_utils import (
    canonicalize_offer_url,
    canonicalize_shop_url,
    offer_id_from_url,
    parse_sales_text,
)

PROFILE_LOCK = threading.Lock()

_MODULEDATA_API = "mtop.alisite.cbu.winport.sync.moduledata.get"
_MMGA_API = "mtop.1688.mmga.offerdetail.service"
_SHOPCARD_API = "mtop.1688.moga.pc.shopcard"

_ENRICH_NAMESPACE = "1688_offer_enrich"
_ENRICH_TTL = 7 * 24 * 3600
_ENRICH_STATIC_FIELDS = (
    "title",
    "image_url",
    "shop_name",
    "quality_rate",
    "rebuy_rate",
    "shop_return_rate",
    "delivery_48h_rate",
    "category",
    "shop_fans",
    "listed_at",
    "dropship_heat",
    "dropship_7d",
    "dropship_30d",
    "attrs_json",
)

_ENRICH_CACHE_STORE: CacheStore | None = None


def _default_enrich_cache_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".sync-data-cache.json"


def _enrich_cache_store() -> CacheStore:
    global _ENRICH_CACHE_STORE
    if _ENRICH_CACHE_STORE is None:
        _ENRICH_CACHE_STORE = CacheStore(
            _default_enrich_cache_path(),
            default_ttl=_ENRICH_TTL,
        )
    return _ENRICH_CACHE_STORE


def _enrichment_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Static, rarely-changing fields worth caching across sync runs."""
    return {k: row[k] for k in _ENRICH_STATIC_FIELDS if row.get(k) not in (None, "")}


def _apply_cached_enrichment(row: dict[str, Any], cached: dict[str, Any] | None) -> bool:
    """Merge cached static fields into ``row``; True when a hit should skip detail fetch."""
    if not isinstance(cached, dict) or not cached:
        return False
    for key in _ENRICH_STATIC_FIELDS:
        if cached.get(key) not in (None, "") and row.get(key) in (None, ""):
            row[key] = cached[key]
    return True


def _load_enrich_cache(store: CacheStore, *, tenant_id: int, offer_id: str) -> dict[str, Any] | None:
    return store.get(_ENRICH_NAMESPACE, f"{int(tenant_id)}:{offer_id}")


def _save_enrich_cache(store: CacheStore, *, tenant_id: int, offer_id: str, row: dict[str, Any]) -> None:
    fields = _enrichment_fields(row)
    if fields:
        store.set(_ENRICH_NAMESPACE, f"{int(tenant_id)}:{offer_id}", fields)


def _offer_detail_cache_enabled(offer_id: str, pinned: list[str]) -> bool:
    """Pinned offers are monitored targets and must always be fetched fresh."""
    return offer_id not in pinned


def crawl_shop(*, tenant_id: int, target: dict, max_products: int) -> dict[str, Any]:
    config = _target_config(target)
    pinned = [str(x) for x in (config.get("pinned_offer_ids") or [])]
    top_n = max(1, min(int(config.get("top_n") or max_products or 20), int(max_products or 20)))
    raw_url = str(target.get("target_url") or "")
    strategy = str(target.get("crawl_strategy") or "1688_shop_topn")

    if strategy == "1688_pinned_offers":
        oid = offer_id_from_url(raw_url)
        if not oid:
            raise ValueError(f"not a 1688 offer url: {raw_url}")
        shop_url = ""
        offers = [_empty_offer(oid, canonicalize_offer_url(raw_url))]
        shop: dict[str, Any] = {}
    else:
        shop_url = canonicalize_shop_url(raw_url)
        offers: list[dict[str, Any]] = []
        shop = {}

    with PROFILE_LOCK:
        from agent.alibaba1688_tasks import _close, _launch, _looks_logged_in

        pw = context = page = None
        try:
            pw, context, page = _launch(tenant_id, headless=True, goto="https://work.1688.com/")
            if not _looks_logged_in(page, context):
                raise RuntimeError("MONITOR_AUTH_REQUIRED: 1688 未登录或登录已失效")
            page.wait_for_timeout(4000)
            if shop_url:
                shop, offers = _fetch_shop_offers(page, shop_url, top_n)
            rows = _fetch_offer_details(page, offers, pinned, tenant_id=tenant_id)
        finally:
            _close(pw, context)

    rows.sort(key=lambda r: (r.get("is_pinned") == 0, r.get("rank") or 999))
    return {
        "platform": "1688",
        "snapshot_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "products": rows,
        "shop": shop,
        "meta": {"member_id": shop.get("member_id", ""), "top_n": top_n, "pinned": pinned},
    }


def _target_config(target: dict) -> dict[str, Any]:
    raw = target.get("config_json") or "{}"
    try:
        return json.loads(str(raw))
    except Exception:
        return {}


def _empty_offer(oid: str, url: str) -> dict[str, Any]:
    return {
        "offer_id": oid,
        "title": "",
        "price": "",
        "sale_text": "",
        "total_sales": 0,
        "rank": 0,
        "listed_at": "",
        "url": url,
        "image_url": "",
        "status": "",
        "expired": False,
        "rebuy_rate": "",
        "raw_json": "",
    }


def _fetch_shop_offers(page, shop_url: str, top_n: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    page.goto(shop_url, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(5000)
    _assert_no_risk(page)
    member_id = _extract_member_id(page)
    if not member_id:
        raise RuntimeError("MONITOR_PARSE_FAILED: 店铺页未返回 memberId")

    from agent.alibaba1688_order_tasks import _mtop

    payload = {
        "componentKey": "wp_pc_auto_offer_big",
        "params": json.dumps(
            {
                "memberId": member_id,
                "appdata": {
                    "source": "index",
                    "count": str(top_n),
                    "sortType": "tradenumdown",
                    "catId": "-1",
                },
            },
            ensure_ascii=False,
        ),
    }
    resp = _mtop(page, _MODULEDATA_API, payload)
    parsed = parse_shop_list_response(json.dumps(resp, ensure_ascii=False))
    offers = parsed["offers"][:top_n]
    if not offers:
        raise RuntimeError("MONITOR_NO_PRODUCTS: 店铺页未返回商品列表")
    return {"member_id": member_id, "shop_url": shop_url}, offers


def _extract_member_id(page) -> str:
    try:
        value = page.evaluate(
            "() => window.memberId || (window.g_config && window.g_config.memberId) || ''"
        )
        if value:
            return str(value)
    except Exception:
        pass
    try:
        html = page.content()
        m = re.search(r"memberId\s*[=:]\s*[\"'](b2b-[a-zA-Z0-9]+)[\"']", html)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""


def _fetch_offer_details(
    page,
    offers: list[dict[str, Any]],
    pinned: list[str],
    *,
    tenant_id: int,
) -> list[dict[str, Any]]:
    rows = {str(o["offer_id"]): dict(o) for o in offers}
    for oid in pinned:
        if oid not in rows:
            rows[oid] = _empty_offer(oid, f"https://detail.1688.com/offer/{oid}.html")
    out: list[dict[str, Any]] = []
    for oid in list(rows):
        row = rows[oid]
        row["is_pinned"] = 1 if oid in pinned else 0
        if _offer_detail_cache_enabled(oid, pinned):
            cached = _load_enrich_cache(
                _enrich_cache_store(),
                tenant_id=tenant_id,
                offer_id=oid,
            )
            if _apply_cached_enrichment(row, cached):
                out.append(row)
                continue
        captured: list[str] = []

        def on_response(resp) -> None:
            try:
                url = str(resp.url or "")
                if _MMGA_API in url or _SHOPCARD_API in url:
                    text = resp.text()
                    if text:
                        captured.append(text)
            except Exception:
                pass

        page.on("response", on_response)
        try:
            page.goto(f"https://detail.1688.com/offer/{oid}.html", wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(4000)
            _assert_no_risk(page)
        finally:
            page.remove_listener("response", on_response)
        try:
            from agent.alibaba1688_order_tasks import _mtop

            resp = _mtop(
                page,
                _MMGA_API,
                {
                    "mmgaRequest": {
                        "serviceName": "compareOfferSelectListService",
                        "offerId": int(oid),
                        "queryType": "similar",
                        "querySource": "PC",
                        "needSort": True,
                    }
                },
            )
            captured.append(json.dumps(resp, ensure_ascii=False))
        except Exception:
            pass

        try:
            detail = parse_offer_detail_responses(captured)
            shop = {}
            for text in captured:
                candidate = parse_shopcard_response(text)
                if candidate.get("shop_name"):
                    shop = candidate
                    break
            row = _merge_detail(row, detail, shop)
        except Exception:
            # 单商品失败不阻断整店：保留列表已有字段，继续下一个
            pass
        if _offer_detail_cache_enabled(oid, pinned):
            _save_enrich_cache(
                _enrich_cache_store(),
                tenant_id=tenant_id,
                offer_id=oid,
                row=row,
            )
        out.append(row)
        time.sleep(0.8)
    return out


def _assert_no_risk(page) -> None:
    try:
        url = str(page.url or "")
        if "punish" in url or "_____tmd_____" in url:
            raise RuntimeError("MONITOR_RISK_BLOCKED: 1688 风控验证页（punish/captcha），已退避")
        content = page.content()[:3000]
        if "rgv587_flag" in content or "验证码" in content or "captcha" in content.lower():
            raise RuntimeError("MONITOR_RISK_BLOCKED: 1688 风控验证页（punish/captcha），已退避")
    except RuntimeError:
        raise
    except Exception:
        pass


def _merge_detail(row: dict[str, Any], detail: dict[str, Any], shop: dict[str, Any]) -> dict[str, Any]:
    cur = detail.get("current") or {}
    if cur:
        if not row.get("title"):
            row["title"] = str(cur.get("title") or "")
        if not row.get("price"):
            row["price"] = str(cur.get("price") or "")
        if not row.get("image_url") and cur.get("imageUrl"):
            row["image_url"] = str(cur.get("imageUrl") or "")
        if not row.get("sale_text"):
            row["sale_text"] = str(cur.get("saleText") or "")
        row["total_sales"] = max(
            int(row.get("total_sales") or 0),
            parse_sales_text(cur.get("saleText")),
        )
    if detail.get("attrs_json"):
        row["attrs_json"] = detail["attrs_json"]
    if detail.get("rebuy_rate"):
        row["rebuy_rate"] = detail["rebuy_rate"]
    for item in detail.get("advise") or []:
        key = str(item.get("key") or "")
        value = str(item.get("value") or "")
        if key == "dfPoint":
            try:
                row["dropship_heat"] = int(float(value))
            except ValueError:
                pass
        elif key == "orderCnt30d":
            row["dropship_30d"] = value
        elif key == "orderCnt7d":
            row["dropship_7d"] = value
        elif key == "offerPublishDate" and not row.get("listed_at"):
            row["listed_at"] = value
    if shop.get("shop_name"):
        for key in ("shop_name", "shop_url", "shop_fans", "quality_rate", "shop_return_rate", "delivery_48h_rate", "category"):
            if shop.get(key):
                row.setdefault(key, shop[key])
    row["raw_json"] = json.dumps(
        {
            "current": cur,
            "attrs": detail.get("attrs_json"),
            "advise": detail.get("advise"),
            "shop": {k: shop.get(k) for k in ("shop_name", "shop_url", "quality_rate", "shop_return_rate", "delivery_48h_rate", "category", "shop_fans")},
        },
        ensure_ascii=False,
    )
    return row
