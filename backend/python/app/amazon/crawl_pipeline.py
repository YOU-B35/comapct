"""Amazon 运营数据爬取主编排（V2 Pipeline）。"""
from __future__ import annotations

import time
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app.amazon.composer.metrics_merger import coalesce_ads_summary, merge_ads_metrics
from app.amazon.composer.product_composer import (
    compose_product_rows,
    enrich_product_rows,
    merge_campaign_ads_into_products,
    merge_product_catalog,
)
from app.amazon.crawlers.account import (
    cases_from_seller_news,
    crawl_account_health_metrics,
    parse_home_metrics,
    parse_home_news_and_cases,
)
from app.amazon.crawlers.business_report import crawl_business_report
from app.amazon.crawlers.orders_v3 import crawl_orders_v3
from app.amazon.sources.amazon_sync_config import (
    ads_dom_fallback_enabled,
    br_dom_fallback_enabled,
    inventory_dom_fallback_enabled,
    report_period_days,
)
from app.amazon.sources.business_report_csv import crawl_business_report_csv
from app.amazon.sources.ads_asin_report_csv import crawl_ads_asin_csv
from app.amazon.sources.data_quality import build_data_quality
from app.amazon.sources.inventory_csv import crawl_inventory_csv
from app.amazon.crawlers.campaign_manager import crawl_ads_data
from app.amazon.crawlers.daily_ops import crawl_cases, crawl_messages, crawl_operational_lists, crawl_reviews
from app.amazon.crawlers.inventory import (
    crawl_home_catalog,
    crawl_inventory_for_asins,
    crawl_inventory_products,
    merge_catalog_sources,
)
from app.amazon.diagnostics import CrawlDiagnostics, PageDiagnostic
from app.amazon.page_urls import HOME_URL
from app.amazon.parsers.seller_pages import EXTRACT_DEEP_BODY_TEXT_JS
from app.amazon.scope_planner import normalize_scope
from app.amazon.session_context import (
    AmazonLoginRequiredError,
    CAPTURE_DIR,
    SessionContext,
    ensure_seller_logged_in_with_wait,
    extract_debug_port,
    looks_logged_in,
    save_capture,
)
from app.ziniao.client import ZiniaoClient, ZiniaoConfig

PRODUCT_SYNC_SCOPES = frozenset({"daily", "insights", "reports"})


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _annotate_product_sync(result: dict[str, Any], scope: str, catalog_count: int, br_count: int) -> None:
    if scope not in PRODUCT_SYNC_SCOPES:
        return
    products = result.get("products") or []
    if products:
        result["product_sync_warning"] = ""
        if br_count > 0 and catalog_count > 0 and br_count < max(3, int(catalog_count * 0.2)):
            result["product_sync_warning"] = "PARTIAL_BR"
        return
    result["product_sync_warning"] = "NO_ASIN_ROWS"


def _empty_result() -> dict[str, Any]:
    return {
        "synced_at": _now_text(),
        "metrics": [],
        "products": [],
        "outbound_orders": [],
        "buyer_messages": [],
        "reviews": [],
        "coupons": [],
        "seller_news": [],
        "shipments": [],
        "cases": [],
        "page_url": "",
        "capture_path": "",
        "merchant_id": "",
        "page_diagnostics": [],
        "result_summary": {},
    }


def _record(
    diagnostic: CrawlDiagnostics,
    key: str,
    url: str,
    rows: list,
    started: float,
    warning: str = "",
    *,
    capture_path: str = "",
) -> None:
    diagnostic.add(
        PageDiagnostic(
            key=key,
            url=url,
            ok=bool(rows) and not warning,
            rows=len(rows) if isinstance(rows, list) else 0,
            duration_ms=int((time.time() - started) * 1000),
            warning=warning,
            capture_path=capture_path,
        )
    )


def _load_inventory_products(
    page,
    *,
    store_name: str,
    use_csv: bool,
) -> tuple[list[dict[str, Any]], str, str, str]:
    if use_csv:
        csv_result = crawl_inventory_csv(page, store_name=store_name)
        if csv_result.rows:
            return csv_result.rows, "inv_csv", csv_result.page_url, ""
        if inventory_dom_fallback_enabled():
            dom_rows = crawl_inventory_products(page, store_name=store_name, max_pages=3, fast=False)
            return dom_rows, "inventory_all_dom", page.url, "" if dom_rows else csv_result.warning
        return [], "inv_csv", csv_result.page_url, csv_result.warning or "ZERO_ROWS"

    dom_rows = crawl_inventory_products(page, store_name=store_name, max_pages=3, fast=False)
    return dom_rows, "inventory_all", page.url, "" if dom_rows else "ZERO_ROWS"


def _load_ads_campaigns(
    page,
    *,
    store_name: str,
    merchant_id: str,
    use_csv: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any], str, str, str]:
    if use_csv:
        csv_result = crawl_ads_asin_csv(
            page,
            store_name=store_name,
            merchant_id=merchant_id,
            period_days=report_period_days(),
        )
        if csv_result.rows:
            return csv_result.rows, {}, csv_result.merchant_id, "ads_csv", ""
        if ads_dom_fallback_enabled():
            summary, campaigns, resolved = crawl_ads_data(page, merchant_id=merchant_id, fast=False)
            return campaigns, summary, resolved, "ads_campaign_manager_dom", "" if campaigns else csv_result.warning
        return [], {}, csv_result.merchant_id, "ads_csv", csv_result.warning or "ADS_CSV_EMPTY"

    summary, campaigns, resolved = crawl_ads_data(page, merchant_id=merchant_id, fast=False)
    return campaigns, summary, resolved, "ads_campaign_manager", "" if campaigns else "ZERO_ROWS"


def _load_business_report_products(
    page,
    *,
    store_name: str,
    use_csv: bool,
) -> tuple[list[dict[str, Any]], str, str, int, str]:
    """返回 (rows, diag_key, page_url, duration_ms, warning)。"""
    if use_csv:
        started = time.time()
        csv_result = crawl_business_report_csv(page, store_name=store_name)
        if csv_result.rows:
            return (
                csv_result.rows,
                "br_csv",
                csv_result.page_url,
                csv_result.duration_ms or int((time.time() - started) * 1000),
                "",
            )
        if br_dom_fallback_enabled():
            dom_rows = crawl_business_report(page, store_name=store_name, fast=False)
            return (
                dom_rows,
                "br_child_asin_dom",
                page.url,
                int((time.time() - started) * 1000),
                "" if dom_rows else csv_result.warning or "ZERO_ROWS",
            )
        return (
            [],
            "br_csv",
            csv_result.page_url,
            csv_result.duration_ms,
            csv_result.warning or "ZERO_ROWS",
        )

    started = time.time()
    dom_rows = crawl_business_report(page, store_name=store_name, fast=False)
    return (
        dom_rows,
        "br_child_asin",
        page.url,
        int((time.time() - started) * 1000),
        "" if dom_rows else "ZERO_ROWS",
    )


def run_crawl(
    *,
    scope: str = "account_health",
    browser_id: str = "",
    browser_oauth: str = "",
    store_name: str = "",
    merchant_id: str = "",
) -> dict[str, Any]:
    if not browser_id and not browser_oauth:
        raise ValueError("缺少 browser_id 或 browser_oauth")

    started_at = time.time()
    normalized_scope = normalize_scope(scope)
    print(
        f"[AmazonPipeline] begin scope={normalized_scope} browser_id={browser_id or '-'} "
        f"oauth={'yes' if bool(browser_oauth) else 'no'} store={store_name or '-'} merchant={merchant_id or '-'}",
        file=sys.stderr,
    )
    ziniao = ZiniaoClient(ZiniaoConfig.from_env())
    ziniao.ensure_webdriver_client(wait_seconds=20)
    start_result = ziniao.start_browser(
        browser_id=browser_id or None,
        browser_oauth=browser_oauth or None,
    )
    debug_port = extract_debug_port(start_result)
    print(f"[AmazonPipeline] CDP ready port={debug_port}", file=sys.stderr)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("缺少 playwright，请执行 pip install -r backend/python/requirements.txt") from exc

    result = _empty_result()
    diagnostics = CrawlDiagnostics()
    _login_required = False

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
        try:
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(90000)
            ctx = SessionContext(page, store_name=store_name, merchant_id=merchant_id)

            started = time.time()
            print(f"[AmazonPipeline] goto home: {HOME_URL}", file=sys.stderr)
            page.goto(HOME_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(3000 if normalized_scope == "reports" else 5000)
            try:
                home_text = page.evaluate(EXTRACT_DEEP_BODY_TEXT_JS) or page.inner_text("body")
            except Exception:
                home_text = page.inner_text("body")
            result["page_url"] = page.url
            try:
                home_text = ensure_seller_logged_in_with_wait(
                    page,
                    body_text=home_text,
                    store_name=store_name,
                )
            except AmazonLoginRequiredError:
                _login_required = True
                raise
            result["page_url"] = page.url
            ctx.ensure_merchant_id()
            _record(diagnostics, "home", HOME_URL, [{"ok": True}], started)
            print(
                f"[AmazonPipeline] home ok elapsed_ms={int((time.time() - started) * 1000)} "
                f"url={page.url}",
                file=sys.stderr,
            )

            if normalized_scope in {"account_health", "daily", "reports"}:
                result["metrics"] = parse_home_metrics(home_text)
                if normalized_scope in {"daily", "reports"}:
                    seller_news, cases = parse_home_news_and_cases(home_text)
                    if seller_news:
                        result["seller_news"] = seller_news
                    if cases:
                        result["cases"] = cases

            report_products: list[dict[str, Any]] = []
            inventory_products: list[dict[str, Any]] = []
            order_rows: list[dict[str, Any]] = []
            br_count = 0
            catalog_count = 0
            inv_count = 0
            ads_count = 0

            if normalized_scope in {"daily", "reports"}:
                use_br_csv = normalized_scope == "reports"
                print(f"[AmazonPipeline] product scopes start use_csv={use_br_csv}", file=sys.stderr)
                started = time.time()
                home_products = crawl_home_catalog(page)
                _record(diagnostics, "home_catalog", HOME_URL, home_products, started)
                print(f"[AmazonPipeline] home_catalog rows={len(home_products)}", file=sys.stderr)

                br_started = time.time()
                report_products, br_key, br_url, _br_ms, br_warning = _load_business_report_products(
                    page,
                    store_name=store_name,
                    use_csv=use_br_csv,
                )
                br_count = len(report_products)
                _record(
                    diagnostics,
                    br_key,
                    br_url,
                    report_products,
                    br_started,
                    br_warning,
                )
                print(
                    f"[AmazonPipeline] br rows={br_count} key={br_key} warning={br_warning or '-'}",
                    file=sys.stderr,
                )

                inv_started = time.time()
                inventory_products, inv_key, inv_url, inv_warning = _load_inventory_products(
                    page,
                    store_name=store_name,
                    use_csv=use_br_csv,
                )
                inv_count = len(inventory_products)
                catalog_count = inv_count
                _record(
                    diagnostics,
                    inv_key,
                    inv_url,
                    inventory_products,
                    inv_started,
                    inv_warning,
                )
                print(
                    f"[AmazonPipeline] inventory rows={inv_count} key={inv_key} warning={inv_warning or '-'}",
                    file=sys.stderr,
                )

                if use_br_csv and report_products:
                    known = {str(r.get("asin") or "").upper(): r for r in inventory_products if r.get("asin")}
                    missing_asins = [
                        str(p.get("asin") or "").upper()
                        for p in report_products
                        if p.get("asin") and int(str(known.get(str(p.get("asin") or "").upper(), {}).get("inventory") or "0")) <= 0
                    ]
                    if missing_asins:
                        search_started = time.time()
                        searched = crawl_inventory_for_asins(
                            page,
                            missing_asins,
                            store_name=store_name,
                            max_asins=30,
                        )
                        if searched:
                            inventory_products = merge_product_catalog(inventory_products, searched)
                            inv_count = len(inventory_products)
                            _record(
                                diagnostics,
                                "inventory_asin_search",
                                inv_url,
                                searched,
                                search_started,
                                "",
                            )

                inventory_products = merge_catalog_sources(
                    inventory_products,
                    home_products,
                    store_name=store_name,
                    page=page if not (use_br_csv and br_count >= 5) else None,
                )
                catalog_count = max(catalog_count, len(inventory_products))

                order_rows: list[dict[str, Any]] = []
                if not use_br_csv:
                    started = time.time()
                    order_rows = crawl_orders_v3(page)
                    if order_rows:
                        result["outbound_orders"] = order_rows
                    _record(
                        diagnostics,
                        "orders_all",
                        "orders-v3/*",
                        order_rows,
                        started,
                        "" if order_rows else "ZERO_ROWS",
                    )

                composed = compose_product_rows(
                    report_products,
                    inventory_products,
                    home_products,
                    None if use_br_csv else order_rows,
                )
                if composed:
                    result["products"] = enrich_product_rows(composed)

                ads_started = time.time()
                ad_campaigns, ads_summary, resolved_merchant, ads_key, ads_warning = _load_ads_campaigns(
                    page,
                    store_name=store_name,
                    merchant_id=ctx.merchant_id,
                    use_csv=use_br_csv,
                )
                ads_count = len(ad_campaigns)
                ctx.merchant_id = resolved_merchant or ctx.merchant_id
                result["merchant_id"] = ctx.merchant_id
                _record(
                    diagnostics,
                    ads_key,
                    page.url,
                    ad_campaigns,
                    ads_started,
                    ads_warning,
                )
                print(
                    f"[AmazonPipeline] ads rows={ads_count} key={ads_key} warning={ads_warning or '-'}",
                    file=sys.stderr,
                )
                ads_summary = coalesce_ads_summary(ads_summary, result.get("metrics"))
                if ads_summary:
                    result["metrics"] = merge_ads_metrics(result.get("metrics") or [], ads_summary)
                if result.get("products"):
                    if ad_campaigns:
                        result["products"] = merge_campaign_ads_into_products(
                            result.get("products") or [],
                            ad_campaigns,
                        )
                    result["products"] = enrich_product_rows(result["products"])

            if normalized_scope == "daily":
                started = time.time()
                coupons, shipments = crawl_operational_lists(page)
                if coupons:
                    result["coupons"] = coupons
                if shipments:
                    result["shipments"] = shipments
                _record(diagnostics, "coupons", "promotions/*", coupons, started)
                _record(diagnostics, "shipments", "fba/inbound/*", shipments, time.time())
                if not result["cases"]:
                    started = time.time()
                    cases = crawl_cases(page)
                    if cases:
                        result["cases"] = cases
                    _record(diagnostics, "cases", "case-lobby/*", cases, started)
                if not result["cases"] and result.get("seller_news"):
                    result["cases"] = cases_from_seller_news(result["seller_news"])

            if normalized_scope == "daily":
                started = time.time()
                messages = crawl_messages(page)
                if messages:
                    result["buyer_messages"] = messages
                _record(diagnostics, "messages", page.url, messages, started)

                started = time.time()
                reviews = crawl_reviews(page)
                if reviews:
                    result["reviews"] = reviews
                _record(diagnostics, "reviews", page.url, reviews, started)

                if not result["cases"]:
                    _, cases = parse_home_news_and_cases(home_text)
                    result["cases"] = cases
                if not result["cases"]:
                    cases = crawl_cases(page)
                    if cases:
                        result["cases"] = cases
                if not result["cases"] and result.get("seller_news"):
                    result["cases"] = cases_from_seller_news(result["seller_news"])
                if not result.get("coupons") or not result.get("shipments"):
                    coupons, shipments = crawl_operational_lists(page)
                    if coupons and not result.get("coupons"):
                        result["coupons"] = coupons
                    if shipments and not result.get("shipments"):
                        result["shipments"] = shipments

            if normalized_scope == "account_health" and not result["metrics"]:
                started = time.time()
                result["metrics"] = crawl_account_health_metrics(page)
                _record(diagnostics, "account_health", page.url, result["metrics"], started)
                print(
                    f"[AmazonPipeline] account_health metrics_rows={len(result['metrics'])}",
                    file=sys.stderr,
                )

            if not looks_logged_in(home_text, HOME_URL) and not result["metrics"] and not result["products"]:
                capture = save_capture(page, store_name=store_name, suffix="empty")
                raise RuntimeError(f"卖家平台页面未解析到数据，截图: {capture}")

            if normalized_scope == "account_health" and not result["metrics"]:
                capture = save_capture(page, store_name=store_name, suffix="empty")
                raise RuntimeError(f"未解析到账户状况指标，截图: {capture}")

            _annotate_product_sync(result, normalized_scope, catalog_count, br_count)

            diag_summary = diagnostics.summary()
            result["page_diagnostics"] = diag_summary["page_diagnostics"]
            products = result.get("products") or []
            result["data_quality"] = build_data_quality(
                scope=normalized_scope,
                products=products,
                br_count=br_count,
                inv_count=inv_count,
                ads_count=ads_count,
                diagnostics=diag_summary["page_diagnostics"],
                warnings=diag_summary.get("warnings"),
            )
            result["result_summary"] = {
                **diag_summary,
                "products_count": len(products),
                "orders_count": len(result.get("outbound_orders") or []),
                "merchant_id": result.get("merchant_id") or "",
                "data_quality": result.get("data_quality") or {},
            }
            if result.get("product_sync_warning"):
                result["result_summary"]["warnings"] = list(
                    dict.fromkeys(
                        [
                            *diag_summary.get("warnings", []),
                            str(result.get("product_sync_warning")),
                        ]
                    )
                )

            if result.get("product_sync_warning") == "NO_ASIN_ROWS" and not result.get("capture_path"):
                latest = sorted(CAPTURE_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
                if latest:
                    result["capture_path"] = str(latest[0])

            elapsed_ms = int((time.time() - started_at) * 1000)
            print(
                f"[AmazonPipeline] success scope={normalized_scope} elapsed_ms={elapsed_ms} "
                f"products={len(result.get('products') or [])} orders={len(result.get('outbound_orders') or [])}",
                file=sys.stderr,
            )
            return result
        finally:
            try:
                browser.close()
            except Exception:
                pass
            # 登录失效时保留紫鸟浏览器窗口，让用户能手动完成登录/验证码
            if not _login_required:
                try:
                    ziniao.stop_browser(
                        browser_id=browser_id or None,
                        browser_oauth=browser_oauth or None,
                    )
                    print("[AmazonPipeline] stop_browser done", file=sys.stderr)
                except Exception:
                    print("[AmazonPipeline] stop_browser failed", file=sys.stderr)


def crawl_account_health(**kwargs: Any) -> dict[str, Any]:
    return run_crawl(scope="account_health", **kwargs)
