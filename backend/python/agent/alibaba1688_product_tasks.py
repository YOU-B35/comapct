"""1688 product synchronization with category-result enrichment.

The legacy implementation is loaded from the last verified Python 3.11 bytecode
snapshot. This wrapper keeps its public helpers stable while category syncing is
implemented independently and returned as relation sets instead of product tags.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import time
from pathlib import Path
from typing import Any

_LEGACY_PYC = Path(__file__).with_name("alibaba1688_product_tasks_legacy.bin")
_loader = importlib.machinery.SourcelessFileLoader(
    "agent._alibaba1688_product_tasks_legacy_runtime",
    str(_LEGACY_PYC),
)
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
_legacy = importlib.util.module_from_spec(_spec)
_loader.exec_module(_legacy)

for _name, _value in vars(_legacy).items():
    if _name not in {"run_products_sync"} and _name not in globals():
        globals()[_name] = _value

def _sync_legacy_dependencies(*names: str) -> None:
    for name in names:
        if name in globals():
            setattr(_legacy, name, globals()[name])


def _fetch_filtered_manage_mini_pages(*args, **kwargs):
    _sync_legacy_dependencies("_browser_fetch_manage_mini_all")
    return _legacy._fetch_filtered_manage_mini_pages(*args, **kwargs)


def _pause_for_manage_mini_captcha(*args, **kwargs):
    _sync_legacy_dependencies(
        "_goto_manage_spa",
        "_wait_out_manage_mini_captcha",
    )
    return _legacy._pause_for_manage_mini_captcha(*args, **kwargs)


def _fetch_growth_tab_pages(*args, **kwargs):
    _sync_legacy_dependencies(
        "_browser_fetch_manage_mini_all",
        "_resolve_csrf",
        "_goto_manage_spa",
        "_wait_out_manage_mini_captcha",
        "_capture_spa_manage_mini_extras",
    )
    return _legacy._fetch_growth_tab_pages(*args, **kwargs)


def _capture_spa_manage_mini_extras(page, spa_url: str) -> dict[str, str]:
    def matches_manage_mini(response) -> bool:
        try:
            return "manage_mini.vm" in str(response.url or "").lower()
        except Exception:
            return False

    try:
        with page.expect_response(matches_manage_mini, timeout=8_000) as response_info:
            page.goto(spa_url, wait_until="commit", timeout=10_000)
        return _query_extras_from_url(response_info.value.url or "")
    except Exception as exc:
        print(f"[1688Products] quick spa extras capture: {exc}", flush=True)
        return {}


# Verified 2026-08-19 against the live seller SPA (see
# tests/fixtures/alibaba1688/category_tab_captures.json). The platform sends
# lifePeriod=<growth-stage code> + show_type=valid for growth tabs; filter/tags
# query extras are NOT what the SPA uses for those tabs.
GROWTH_TAB_SPECS = (
    {
        "scope": "potential",
        "growth_stage": "qlsp",
        "spa": "https://offer.1688.com/app/pages-group/manage-home/index.html?growthStage=qlsp&lifecycle=valid",
        "life_period": "qlsp",
        "show_type": "valid",
    },
    {
        "scope": "index4",
        "growth_stage": "cgzsspyjg",
        "spa": "https://offer.1688.com/app/pages-group/manage-home/index.html?growthStage=cgzsspyjg&lifecycle=valid",
        "life_period": "cgzsspyjg",
        "show_type": "valid",
    },
    {
        "scope": "yanxuan",
        "growth_stage": "growthyxp",
        "spa": "https://offer.1688.com/app/pages-group/manage-home/index.html?growthStage=growthyxp&lifecycle=valid",
        "life_period": "growthyxp",
        "show_type": "valid",
    },
)


# Verified 2026-08-19 live: status tabs use show_type=expired/auditing/untread,
# sold out adds isSellOut=true, growth tabs use lifePeriod=<growth-stage code>.
# Draft has no manage_mini list on the platform SPA and stays failed (relations
# from the previous successful sync are preserved by Java).
PRODUCT_CATEGORY_SPECS = (
    {"code": "status_on_sale", "kind": "status", "life_period": "all", "show_type": "valid"},
    {"code": "status_pending_list", "kind": "status", "life_period": "all", "show_type": "expired"},
    {"code": "status_sold_out", "kind": "status", "life_period": "all", "show_type": "valid", "extra_qs": {"isSellOut": "true"}},
    {"code": "status_reviewing", "kind": "status", "life_period": "all", "show_type": "auditing"},
    {"code": "status_violation_off", "kind": "status", "life_period": "all", "show_type": "untread"},
    {"code": "status_draft", "kind": "status", "life_period": "all", "show_type": "draft"},
    {"code": "growth_potential", "kind": "growth", "scope": "potential", "life_period": "qlsp", "show_type": "valid"},
    {"code": "growth_yanxuan", "kind": "growth", "scope": "yanxuan", "life_period": "growthyxp", "show_type": "valid"},
    {"code": "growth_index", "kind": "growth", "scope": "index4", "life_period": "cgzsspyjg", "show_type": "valid"},
)


def category_offer_ids(rows: list[dict[str, Any]], catalog_offer_ids: set[str]) -> list[str]:
    offer_ids: list[str] = []
    seen: set[str] = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        offer_id = str(row.get("offerId") or row.get("offer_id") or "").strip()
        if offer_id and offer_id in catalog_offer_ids and offer_id not in seen:
            seen.add(offer_id)
            offer_ids.append(offer_id)
    return offer_ids


def failed_category_result(error_code: str, elapsed_ms: int) -> dict[str, Any]:
    return {
        "status": "failed",
        "error_code": str(error_code or "A1688_CATEGORY_FAILED"),
        "elapsed_ms": max(0, int(elapsed_ms or 0)),
    }


def category_result(
    *,
    code: str,
    rows: list[dict[str, Any]],
    total: int | None,
    catalog_offer_ids: set[str],
    elapsed_ms: int,
) -> dict[str, Any]:
    if total is None and not rows:
        return failed_category_result("A1688_CATEGORY_INVALID_RESPONSE", elapsed_ms)
    fetched_total = int(total or 0) or len(rows or [])
    if total is not None and rows and len(rows) < int(total):
        # Pagination was truncated (platform throttling / page cap). Do not
        # replace the previous successful relations with a partial set.
        return failed_category_result("A1688_CATEGORY_PARTIAL_RESPONSE", elapsed_ms)
    if (
        code.startswith("growth_")
        and len(catalog_offer_ids) >= 20
        and growth_filter_likely_ignored(fetched_total, len(catalog_offer_ids))
    ):
        return failed_category_result("A1688_CATEGORY_FILTER_IGNORED", elapsed_ms)
    offer_ids = category_offer_ids(rows, catalog_offer_ids)
    return {
        "status": "success",
        "count": len(offer_ids),
        "offer_ids": offer_ids,
        "elapsed_ms": max(0, int(elapsed_ms or 0)),
    }


_GROWTH_SPEC_BY_SCOPE = {spec["scope"]: spec for spec in GROWTH_TAB_SPECS}


def _fetch_growth_category_pages(
    page,
    *,
    spec: dict[str, Any],
    csrf: str,
    catalog_unique: int,
    fetch_fn=None,
    capture_fn=None,
    resolve_csrf_fn=None,
):
    filtered_fetch = fetch_fn or _fetch_filtered_manage_mini_pages
    capture = capture_fn or _capture_spa_manage_mini_extras
    resolve_csrf = resolve_csrf_fn or _resolve_csrf
    life_period = str(spec.get("life_period") or "valid")
    extra_qs = dict(spec.get("extra_qs") or {})
    common_kwargs = {
        "csrf": csrf,
        "life_period": life_period,
        "catalog_unique": catalog_unique,
        "show_type": str(spec.get("show_type") or "valid"),
        "stamp_growth_stage": str(spec.get("growth_stage") or ""),
        # Platform caps each manage_mini page at 20 rows regardless of
        # pageSize; request 20/page so pagination reaches the real total
        # (e.g. potential ~479 items) instead of stopping at 200.
        "page_size": 20,
    }
    rows, total, captcha = filtered_fetch(
        page,
        extra_qs=extra_qs,
        **common_kwargs,
    )
    fetched_total = int(total or 0) or len(rows or [])
    if captcha or not growth_filter_likely_ignored(fetched_total, catalog_unique):
        return rows, total, captcha

    captured_qs = capture(page, str(spec.get("spa") or ""))
    if not captured_qs:
        return rows, total, captcha
    retry_qs = dict(captured_qs)
    retry_qs.update(extra_qs)
    refreshed_csrf = resolve_csrf(page) or csrf
    return filtered_fetch(
        page,
        extra_qs=retry_qs,
        **{**common_kwargs, "csrf": refreshed_csrf},
    )


def sync_product_categories(
    page,
    catalog_offer_ids: set[str],
    deadline: float,
    *,
    csrf: str = "",
    fetch_fn=None,
) -> dict[str, dict[str, Any]]:
    filtered_fetch = fetch_fn or _fetch_filtered_manage_mini_pages
    token = csrf or _resolve_csrf(page)
    results: dict[str, dict[str, Any]] = {}
    for spec in PRODUCT_CATEGORY_SPECS:
        code = str(spec["code"])
        started = time.monotonic()
        if time.time() >= deadline:
            results[code] = failed_category_result("A1688_CATEGORY_TIMEOUT", 0)
            continue
        if not token:
            results[code] = failed_category_result("A1688_CATEGORY_CSRF_MISSING", 0)
            continue
        kwargs: dict[str, Any] = {
            "csrf": token,
            "life_period": str(spec.get("life_period") or "all"),
            "catalog_unique": len(catalog_offer_ids),
            "show_type": str(spec.get("show_type") or "valid"),
        }
        if spec.get("extra_qs"):
            kwargs["extra_qs"] = dict(spec["extra_qs"])
        if spec.get("kind") == "growth":
            growth_spec = _GROWTH_SPEC_BY_SCOPE[str(spec["scope"])]
        try:
            if spec.get("kind") == "growth":
                rows, total, captcha = _fetch_growth_category_pages(
                    page,
                    spec=growth_spec,
                    csrf=token,
                    catalog_unique=len(catalog_offer_ids),
                    fetch_fn=filtered_fetch,
                )
            elif code == "status_on_sale" and fetch_fn is None:
                if catalog_offer_ids:
                    # 主目录本身就是 lifePeriod=all&show_type=valid（销售中），
                    # 直接复用，避免再拉 10+ 页触发平台风控。
                    rows = [{"offerId": oid} for oid in sorted(catalog_offer_ids)]
                    total = len(catalog_offer_ids)
                    captcha = False
                else:
                    rows, total, captcha = _browser_fetch_manage_mini_all(page, **kwargs)
            else:
                rows, total, captcha = filtered_fetch(page, **kwargs)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            if captcha:
                results[code] = failed_category_result("A1688_CATEGORY_CAPTCHA", elapsed_ms)
                continue
            results[code] = category_result(
                code=code,
                rows=rows,
                total=total,
                catalog_offer_ids=catalog_offer_ids,
                elapsed_ms=elapsed_ms,
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            result = failed_category_result("A1688_CATEGORY_FETCH_FAILED", elapsed_ms)
            result["error_message"] = str(exc)[:300]
            results[code] = result
    return results


class _CategoryIngestClient:
    def __init__(self, client, *, sync_id: str, categories: dict[str, dict[str, Any]]):
        self._client = client
        self._sync_id = str(sync_id or "")
        self._categories = categories

    def __getattr__(self, name: str):
        return getattr(self._client, name)

    def ingest_1688_products(self, payload: dict[str, Any]):
        enriched = dict(payload or {})
        enriched["sync_id"] = self._sync_id
        enriched["categories"] = self._categories
        enriched["partial"] = any(
            str(result.get("status") or "") != "success"
            for result in self._categories.values()
        )
        return self._client.ingest_1688_products(enriched)


def run_products_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    category_holder: dict[str, dict[str, Any]] = {
        spec["code"]: failed_category_result("A1688_CATEGORY_NOT_RUN", 0)
        for spec in PRODUCT_CATEGORY_SPECS
    }
    original_fetch = _legacy._fetch_manage_mini_pages
    original_goto = _legacy._goto_and_wait_offer_list

    def skip_gateway_enrichment(*_args, **_kwargs) -> None:
        # 分类关系已由 sync_product_categories 独立捕获；旧 gateway 标签富化
        # 需要点击 SPA Tab，易被平台风控弹窗卡住，且前端已不再依赖商品表标签。
        print("[1688Products] skip legacy gateway tag enrichment", flush=True)

    def fetch_with_categories(page, box, *args, **kwargs):
        count = original_fetch(page, box, *args, **kwargs)
        catalog_offer_ids = {
            str(_pick_offer_id(row) or "").strip()
            for row in box.get("rows", [])
            if isinstance(row, dict) and str(_pick_offer_id(row) or "").strip()
        }
        if catalog_offer_ids:
            category_holder.clear()
            category_holder.update(
                sync_product_categories(
                    page,
                    catalog_offer_ids,
                    deadline=time.time() + 90,
                    csrf=_resolve_csrf(page),
                )
            )
        return count

    sync_id = str(task.get("id") or (task.get("payload") or {}).get("sync_id") or "")
    proxy = _CategoryIngestClient(client, sync_id=sync_id, categories=category_holder)
    _legacy._fetch_manage_mini_pages = fetch_with_categories
    _legacy._goto_and_wait_offer_list = skip_gateway_enrichment
    try:
        result = _legacy.run_products_sync(proxy, task)
        result = dict(result or {})
        result["categories"] = category_holder
        result["partial"] = any(
            str(item.get("status") or "") != "success"
            for item in category_holder.values()
        )
        return result
    finally:
        _legacy._fetch_manage_mini_pages = original_fetch
        _legacy._goto_and_wait_offer_list = original_goto
