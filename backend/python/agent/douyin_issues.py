"""Douyin content-issues fetch — frozen paths from Day0 attachment.

See: docs/superpowers/specs/attachments/douyin-issues-xhr.md
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlencode
from app.timezone import SHANGHAI


# Day0 READY sources
VIOLATION_PAGE = "https://fxg.jinritemai.com/ffa/grs/penalty"
VIOLATION_TICKET_API = "https://fxg.jinritemai.com/governance/shop/penalty/v3/get_ticket_list"
PRODUCT_DIAG_PAGE = "https://fxg.jinritemai.com/ffa/g/diagnose"
PRODUCT_DIAG_API = "https://fxg.jinritemai.com/product_diagnose/tproduct/get_diagnose_product_list"

SOURCE_VIOLATION = "violation_xhr"
SOURCE_PRODUCT = "product_diag"

# live / short_video: UNCONFIGURED in Day0 attachment
UNCONFIGURED_SOURCES = ("live", "short_video")


def map_violation_row(raw: dict[str, Any], *, now: str | None = None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    ticket_id = str(raw.get("ticket_id") or "").strip()
    if not ticket_id:
        return None
    info = raw.get("info") if isinstance(raw.get("info"), dict) else {}
    obj = info.get("object") if isinstance(info.get("object"), dict) else {}
    reason = str(raw.get("violation_reason") or "").strip()
    detail_extra = str(info.get("violation_detail") or "").strip()
    detail = reason
    if detail_extra:
        detail = f"{reason}；{detail_extra}" if reason else detail_extra
    if not detail:
        detail = "平台违规工单"

    level = str(raw.get("circumstances_level") or "").strip()
    priority = _priority_from_level(level)

    reported_at = _unix_to_ts(info.get("violation_time")) or (now or "")
    product_name = str(obj.get("object_name") or "").strip()
    sku = str(obj.get("object_id") or "").strip()
    product_image = _first_image(obj.get("object_imgs"), obj.get("object_img"), obj.get("img"))

    return {
        "external_id": ticket_id,
        "type": "violation",
        "type_label": "平台违规",
        "sku": sku,
        "product_name": product_name,
        "product_image": product_image,
        "detail": detail,
        "priority": priority,
        "reported_at": reported_at,
        "source": SOURCE_VIOLATION,
    }


def map_product_diag_row(raw: dict[str, Any], *, now: str | None = None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    product_id = str(raw.get("product_id") or "").strip()
    if not product_id:
        return None
    problem_num = raw.get("problem_num_to_improve")
    try:
        problem_n = int(problem_num) if problem_num is not None else 0
    except (TypeError, ValueError):
        problem_n = 0
    name_docs = raw.get("name_doc") if isinstance(raw.get("name_doc"), list) else []
    affect_docs = raw.get("affect_doc") if isinstance(raw.get("affect_doc"), list) else []
    docs = [str(x).strip() for x in name_docs if str(x).strip()]
    affects = [str(x).strip() for x in affect_docs if str(x).strip()]
    if problem_n <= 0 and not docs:
        return None

    parts = list(docs)
    if affects:
        parts.append("影响：" + "、".join(affects))
    detail = "；".join(parts) if parts else f"待优化问题 {problem_n} 项"
    if problem_n >= 3:
        priority = "high"
    elif problem_n >= 1 or docs:
        priority = "medium"
    else:
        priority = "low"

    return {
        "external_id": f"product:{product_id}",
        "type": "product",
        "type_label": "商品问题",
        "sku": product_id,
        "product_name": str(raw.get("product_name") or "").strip(),
        "product_image": _first_image(raw.get("img"), raw.get("product_pic"), raw.get("main_image")),
        "detail": detail,
        "priority": priority,
        "reported_at": now or "",
        "source": SOURCE_PRODUCT,
    }


def map_issue_row(source: str, raw: dict[str, Any], *, now: str | None = None) -> dict[str, Any] | None:
    if source == "violation":
        return map_violation_row(raw, now=now)
    if source == "product":
        return map_product_diag_row(raw, now=now)
    return None


def _priority_from_level(level: str) -> str:
    if level in {"1", "高", "high", "danger"}:
        return "high"
    if level in {"3", "低", "low", "info"}:
        return "low"
    return "medium"


def _first_image(*candidates: Any) -> str:
    for cand in candidates:
        if isinstance(cand, str) and cand.strip():
            return cand.strip()
        if isinstance(cand, list):
            for item in cand:
                if isinstance(item, str) and item.strip():
                    return item.strip()
                if isinstance(item, dict):
                    url = str(item.get("url") or item.get("src") or item.get("img") or "").strip()
                    if url:
                        return url
    return ""


def _unix_to_ts(value: Any) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return ""
    # ms vs s
    if n > 10_000_000_000:
        n = n // 1000
    try:
        return datetime.fromtimestamp(n, tz=SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, OverflowError, ValueError):
        return ""


def _now_ts() -> str:
    return datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")


def _ok_body(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    code = data.get("code", data.get("st", data.get("errno")))
    try:
        return int(code) == 0
    except (TypeError, ValueError):
        return code in (0, "0", None, "")


def fetch_violation_tickets(page, *, page_size: int = 50, max_pages: int = 5) -> list[dict[str, Any]]:
    import time

    try:
        page.goto(VIOLATION_PAGE, wait_until="domcontentloaded", timeout=90_000)
        time.sleep(0.4)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"ISSUES_PARTIAL: 无法打开处罚中心: {exc}") from exc

    rows: list[dict[str, Any]] = []
    for page_no in range(1, max_pages + 1):
        qs = urlencode({"page": str(page_no), "pageSize": str(page_size)})
        url = f"{VIOLATION_TICKET_API}?{qs}"
        resp = page.request.get(url, timeout=60_000)
        if resp.status >= 400:
            raise RuntimeError(f"ISSUES_PARTIAL: ticket_list HTTP {resp.status}")
        data = resp.json()
        if not _ok_body(data):
            raise RuntimeError(f"ISSUES_PARTIAL: ticket_list code={data.get('code') if isinstance(data, dict) else data}")
        payload = data.get("data") if isinstance(data, dict) else None
        tickets = []
        if isinstance(payload, dict):
            tickets = payload.get("tickets") or []
        elif isinstance(payload, list):
            tickets = payload
        if not isinstance(tickets, list) or not tickets:
            break
        for t in tickets:
            if isinstance(t, dict):
                rows.append(t)
        if len(tickets) < page_size:
            break
        time.sleep(0.2)
    return rows


def fetch_product_diagnose(page, *, page_size: int = 50, max_pages: int = 10) -> list[dict[str, Any]]:
    import time

    try:
        page.goto(PRODUCT_DIAG_PAGE, wait_until="domcontentloaded", timeout=90_000)
        time.sleep(0.4)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"ISSUES_PARTIAL: 无法打开商品诊断: {exc}") from exc

    rows: list[dict[str, Any]] = []
    for page_no in range(1, max_pages + 1):
        qs = urlencode(
            {
                "page": str(page_no),
                "pageSize": str(page_size),
                "is_diagnose_search_v2": "true",
                "appid": "1",
                "_bid": "ffa_goods",
            }
        )
        url = f"{PRODUCT_DIAG_API}?{qs}"
        resp = page.request.get(url, timeout=60_000)
        if resp.status >= 400:
            raise RuntimeError(f"ISSUES_PARTIAL: diagnose_product_list HTTP {resp.status}")
        data = resp.json()
        if not _ok_body(data):
            raise RuntimeError(
                f"ISSUES_PARTIAL: diagnose_product_list code={data.get('code') if isinstance(data, dict) else data}"
            )
        payload = data.get("data") if isinstance(data, dict) else None
        batch: list = []
        if isinstance(payload, list):
            batch = payload
        elif isinstance(payload, dict):
            batch = payload.get("list") or payload.get("products") or []
        if not isinstance(batch, list) or not batch:
            break
        for t in batch:
            if isinstance(t, dict):
                rows.append(t)
        if len(batch) < page_size:
            break
        time.sleep(0.2)
    return rows


def collect_issues(page, context=None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch READY sources; UNCONFIGURED live/short_video → partial."""
    now = _now_ts()
    issues: list[dict[str, Any]] = []
    sources_ok: list[str] = []
    partial_reasons: list[str] = []

    try:
        tickets = fetch_violation_tickets(page)
        for raw in tickets:
            mapped = map_violation_row(raw, now=now)
            if mapped:
                issues.append(mapped)
        sources_ok.append("violation")
        print(f"[DouyinIssues] violation tickets={len(tickets)} mapped={len(issues)}", flush=True)
    except Exception as exc:  # noqa: BLE001
        reason = str(exc)
        if "ISSUES_PARTIAL" not in reason:
            reason = f"ISSUES_PARTIAL: violation:{reason}"
        partial_reasons.append(reason)
        print(f"[DouyinIssues] violation failed: {exc}", flush=True)

    before = len(issues)
    try:
        products = fetch_product_diagnose(page)
        for raw in products:
            mapped = map_product_diag_row(raw, now=now)
            if mapped:
                issues.append(mapped)
        sources_ok.append("product")
        print(
            f"[DouyinIssues] product diag rows={len(products)} mapped_added={len(issues) - before}",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        reason = str(exc)
        if "ISSUES_PARTIAL" not in reason:
            reason = f"ISSUES_PARTIAL: product:{reason}"
        partial_reasons.append(reason)
        print(f"[DouyinIssues] product failed: {exc}", flush=True)

    for src in UNCONFIGURED_SOURCES:
        partial_reasons.append(f"ISSUES_SOURCE_UNCONFIGURED:{src}")

    # Dedupe by external_id
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in issues:
        eid = str(row.get("external_id") or "")
        if not eid or eid in seen:
            continue
        seen.add(eid)
        unique.append(row)

    partial = bool(partial_reasons) or not sources_ok
    meta = {
        "partial": partial,
        "partial_reasons": partial_reasons,
        "sources_ok": sources_ok,
    }
    return unique, meta
