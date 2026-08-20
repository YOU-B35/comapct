"""Douyin Compass product-rank: mapping, fetch, and sync runner.

Probed 2026-08-14 (tenant-5 logged-in profile) against
https://compass.jinritemai.com/shop/chance/rank-product:

Boards (path, not numeric rank_type):
  search       → GET /compass_api/shop/mall/product_rank/search
  product_card → GET /compass_api/shop/mall/product_rank/product_card_hot_v2
  total        → GET /compass_api/shop/product/product_rank/market_hot_sale

Date windows (date_type):
  today     → 1  (实时) — supported by total + product_card;
              search board data_range common_use_type is [20,21,23] only,
              so search/today falls back to date_type=20 (近1天).
  yesterday → 20 (近1天)

Default category: do not change the category picker; capture industry_id /
category_id from the first page XHR (or reuse last known defaults).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")

DOUYIN_COMPASS_RANK_PAGE = "https://compass.jinritemai.com/shop/chance/rank-product"
DOUYIN_COMPASS_RANK_XHR_READY = True

# Competitor product overview (榜单「查看详情」页) — fills 曝光/订单成交 for near-1-day.
COMPETE_PRODUCT_CORE_INDEX_API = (
    "/compass_api/shop/product/compete_product_detail/core_index"
)
COMPETE_CORE_INDEX_SELECTED = (
    "pay_amt,dh_product_show_uv,dh_product_click_uv,pay_ucnt,"
    "dh_product_click_pv_ratio_uv,dh_pay_conversion_click_ratio_uv,"
    "dh_pay_conversion_show_ratio_uv,pay_cnt,pay_combo_cnt,"
    "ad_costed_amt,ad_efficiency,ad_receive_amt,ad_prod_click_cnt"
)
# Top-N products to enrich per board×window (plan A).
COMPETE_ENRICH_TOP_N = 50

# Probed endpoint paths (relative; same cookie jar as compass page).
BOARD_RANK_API: dict[str, str] = {
    "search": "/compass_api/shop/mall/product_rank/search",
    "product_card": "/compass_api/shop/mall/product_rank/product_card_hot_v2",
    "total": "/compass_api/shop/product/product_rank/market_hot_sale",
}

# Kept for Task-3/4 contract naming (path key, not numeric).
BOARD_RANK_TYPE: dict[str, Any] = {
    "search": "search",
    "product_card": "product_card_hot_v2",
    "total": "market_hot_sale",
}

DATE_WINDOW_DATE_TYPE: dict[str, Any] = {
    "today": 1,
    "yesterday": 20,
}

# search_product_rank data_range.common_use_type = [20, 21, 23] (no realtime).
SEARCH_DATE_WINDOW_DATE_TYPE: dict[str, int] = {
    "today": 20,
    "yesterday": 20,
}

_BOARD_ALIASES: dict[str, str] = {
    "search": "search",
    "search_rank": "search",
    "搜索": "search",
    "搜索榜": "search",
    "product_card": "product_card",
    "productcard": "product_card",
    "商品卡": "product_card",
    "商品卡榜": "product_card",
    "total": "total",
    "总榜": "total",
}

_DATE_WINDOW_ALIASES: dict[str, str] = {
    "today": "today",
    "realtime": "today",
    "今日": "today",
    "今日实时": "today",
    "yesterday": "yesterday",
    "昨日": "yesterday",
    "近1天": "yesterday",
}


def normalize_board(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return "total"
    if text in _BOARD_ALIASES:
        return _BOARD_ALIASES[text]
    lowered = text.lower()
    if lowered in _BOARD_ALIASES:
        return _BOARD_ALIASES[lowered]
    if lowered in ("search", "product_card", "total"):
        return lowered
    return text


def normalize_date_window(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return "today"
    if text in _DATE_WINDOW_ALIASES:
        return _DATE_WINDOW_ALIASES[text]
    lowered = text.lower()
    if lowered in _DATE_WINDOW_ALIASES:
        return _DATE_WINDOW_ALIASES[lowered]
    if lowered in ("today", "yesterday"):
        return lowered
    return text


def _pick(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def map_rank_row(item: dict[str, Any], rank_no: int) -> dict[str, Any]:
    """Map a Compass rank list row to ingest-friendly snake_case fields.

    Accepts both snake_case and camelCase keys. Nested ``raw`` preserves the
    original item for Java ``raw_json``.
    """
    src = item if isinstance(item, dict) else {}
    product_id = str(
        _pick(src, "product_id", "productId", "id", "product_id_str") or ""
    ).strip()
    product_name = str(
        _pick(src, "product_name", "productName", "name", "title") or ""
    ).strip()
    shop_name = str(_pick(src, "shop_name", "shopName", "author_name") or "").strip()
    main_image = str(
        _pick(src, "main_image", "mainImage", "product_pic_url", "image", "img") or ""
    ).strip()
    category_path = str(
        _pick(src, "category_path", "categoryPath", "category_name", "categoryName") or ""
    ).strip()

    click_cnt = _as_float(
        _pick(src, "click_cnt", "clickCnt", "product_click_cnt", "productClickCnt")
    )
    pay_amt = _as_float(_pick(src, "pay_amt", "payAmt"))
    pay_cnt = _as_float(_pick(src, "pay_cnt", "payCnt", "deal_cnt", "dealCnt"))
    click_pay_cvr = _as_float(
        _pick(
            src,
            "click_pay_cvr",
            "clickPayCvr",
            "product_click_pay_cnt_ratio",
            "productClickPayCntRatio",
        )
    )
    show_cnt = _as_float(
        _pick(src, "show_cnt", "showCnt", "product_show_cnt", "productShowCnt")
    )
    order_cnt = _as_float(
        _pick(src, "order_cnt", "orderCnt", "pay_order_cnt", "payOrderCnt")
    )
    deal_cnt = _as_float(_pick(src, "deal_cnt", "dealCnt", "pay_cnt", "payCnt"))

    explicit_rank = _pick(src, "rank_no", "rankNo", "rank")
    resolved_rank = int(rank_no)
    if explicit_rank not in (None, ""):
        try:
            resolved_rank = int(explicit_rank)
        except (TypeError, ValueError):
            resolved_rank = int(rank_no)

    return {
        "product_id": product_id,
        "product_name": product_name,
        "shop_name": shop_name,
        "main_image": main_image,
        "category_path": category_path,
        "rank_no": resolved_rank,
        "pay_amt": pay_amt,
        "click_cnt": click_cnt,
        "pay_cnt": pay_cnt,
        "click_pay_cvr": click_pay_cvr,
        "show_cnt": show_cnt,
        "order_cnt": order_cnt,
        "deal_cnt": deal_cnt,
        "raw": src,
    }


def _scale_metric(value: float, unit: Any) -> float:
    """Normalize Compass metric units to display numbers (yuan / ratio / count)."""
    if unit in (3, "3", "price"):
        # unit=3 / price → fen
        return round(value / 100.0, 2)
    if unit in (4, "4", "ratio"):
        return float(value)
    return float(value)


def _mid_value_range(node: Any) -> float | None:
    if not isinstance(node, dict) or not node:
        return None
    vr = node.get("value_range")
    if isinstance(vr, list) and vr:
        vals: list[float] = []
        for item in vr:
            if not isinstance(item, dict) or item.get("value") in (None, ""):
                continue
            try:
                vals.append(_scale_metric(float(item["value"]), item.get("unit")))
            except (TypeError, ValueError):
                continue
        if not vals:
            return None
        return round(sum(vals) / len(vals), 4)
    if "value" in node and isinstance(node.get("value"), (int, float)):
        try:
            return _scale_metric(float(node["value"]), node.get("unit"))
        except (TypeError, ValueError):
            return None
    return None


def _compete_metric_mid(node: Any) -> float | None:
    """Parse compete_product_detail/core_index metric node.

    Competitor metrics usually put the usable band in ``extra_value.lower/upper``
    while ``value`` is 0 / placeholder.
    """
    if not isinstance(node, dict) or not node:
        return None
    extra = node.get("extra_value") if isinstance(node.get("extra_value"), dict) else {}
    vals: list[float] = []
    for side_key in ("lower", "upper"):
        side = extra.get(side_key) if isinstance(extra.get(side_key), dict) else None
        if not side or side.get("value") in (None, ""):
            continue
        try:
            vals.append(_scale_metric(float(side["value"]), side.get("unit")))
        except (TypeError, ValueError):
            continue
    if vals:
        return round(sum(vals) / len(vals), 4)
    # Own-shop style exact value
    value = node.get("value") if isinstance(node.get("value"), dict) else None
    if value and value.get("value") not in (None, ""):
        try:
            return _scale_metric(float(value["value"]), value.get("unit"))
        except (TypeError, ValueError):
            return None
    # Fallback: value_range shape
    return _mid_value_range(node)


def parse_compete_core_index(body: dict[str, Any]) -> dict[str, float | None]:
    """Extract show_cnt (曝光人数) + order_cnt (成交订单数) from core_index body."""
    out: dict[str, float | None] = {"show_cnt": None, "order_cnt": None, "deal_cnt": None}
    if not isinstance(body, dict):
        return out
    data = body.get("data")
    metrics = None
    # Shape A: { data: [ { metrics: {...} } ] }
    if isinstance(data, list) and data and isinstance(data[0], dict):
        metrics = data[0].get("metrics") if isinstance(data[0].get("metrics"), dict) else None
    # Shape B: { data: { data: [ { metrics } ], attributes: [...] } }
    elif isinstance(data, dict):
        if isinstance(data.get("metrics"), dict):
            metrics = data.get("metrics")
        else:
            inner = data.get("data")
            if isinstance(inner, list) and inner and isinstance(inner[0], dict):
                metrics = inner[0].get("metrics") if isinstance(inner[0].get("metrics"), dict) else None
            elif isinstance(inner, dict) and isinstance(inner.get("metrics"), dict):
                metrics = inner.get("metrics")
    # Shape C: root already { attributes, data:[{metrics}] }
    if metrics is None and isinstance(body.get("data"), list) is False:
        if isinstance(body.get("metrics"), dict):
            metrics = body.get("metrics")
    if not isinstance(metrics, dict):
        return out
    out["show_cnt"] = _compete_metric_mid(
        metrics.get("dh_product_show_uv")
        or metrics.get("product_show_ucnt")
        or metrics.get("show_cnt")
    )
    out["order_cnt"] = _compete_metric_mid(metrics.get("pay_cnt"))
    out["deal_cnt"] = _compete_metric_mid(metrics.get("pay_combo_cnt"))
    return out


def enrich_products_with_compete_core_index(
    page,
    products: list[dict[str, Any]],
    *,
    date_window: str,
    top_n: int = COMPETE_ENRICH_TOP_N,
) -> dict[str, int]:
    """Fill missing show_cnt / order_cnt via compete_product_detail/core_index (Top N)."""
    dw = normalize_date_window(date_window)
    date_type = int(DATE_WINDOW_DATE_TYPE.get(dw) or 20)
    begin_date, end_date, _report = _date_bounds(date_type)
    stats = {"attempted": 0, "filled_show": 0, "filled_order": 0, "failed": 0, "skipped": 0}
    if not products or not page:
        return stats

    targets = products[: max(0, int(top_n or 0))]
    for row in targets:
        if not isinstance(row, dict):
            stats["skipped"] += 1
            continue
        need_show = row.get("show_cnt") is None
        need_order = row.get("order_cnt") is None
        if not need_show and not need_order:
            stats["skipped"] += 1
            continue
        product_id = str(row.get("product_id") or "").strip()
        if not product_id:
            stats["skipped"] += 1
            continue
        stats["attempted"] += 1
        params = {
            "product_id": product_id,
            "begin_date": begin_date,
            "end_date": end_date,
            "date_type": str(date_type),
            "sale_type": "0",
            "content_type": "0",
            "index_selected": COMPETE_CORE_INDEX_SELECTED,
        }
        try:
            body = _page_fetch_json(page, COMPETE_PRODUCT_CORE_INDEX_API, params)
            parsed = parse_compete_core_index(body)
            if need_show and parsed.get("show_cnt") is not None:
                row["show_cnt"] = parsed["show_cnt"]
                stats["filled_show"] += 1
            if need_order and parsed.get("order_cnt") is not None:
                row["order_cnt"] = parsed["order_cnt"]
                stats["filled_order"] += 1
            # Optional: improve deal_cnt if still empty
            if row.get("deal_cnt") is None and parsed.get("deal_cnt") is not None:
                row["deal_cnt"] = parsed["deal_cnt"]
            if parsed.get("show_cnt") is None and parsed.get("order_cnt") is None:
                stats["failed"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["failed"] += 1
            print(
                f"[DouyinCompassRank] compete core_index fail product={product_id}: {exc}",
                flush=True,
            )
        time.sleep(0.15)
    print(
        f"[DouyinCompassRank] compete enrich {dw}: "
        f"attempted={stats['attempted']} show={stats['filled_show']} "
        f"order={stats['filled_order']} failed={stats['failed']} skipped={stats['skipped']}",
        flush=True,
    )
    return stats


def _cell_range_mid(cell: Any) -> float | None:
    if not isinstance(cell, dict):
        return None
    iv = cell.get("index_values") if isinstance(cell.get("index_values"), dict) else {}
    extra = iv.get("extra_value") if isinstance(iv.get("extra_value"), dict) else {}
    lower = extra.get("lower") if isinstance(extra.get("lower"), dict) else None
    upper = extra.get("upper") if isinstance(extra.get("upper"), dict) else None
    vals: list[float] = []
    for side in (lower, upper):
        if not side or side.get("value") in (None, ""):
            continue
        try:
            vals.append(_scale_metric(float(side["value"]), side.get("unit")))
        except (TypeError, ValueError):
            continue
    if vals:
        return round(sum(vals) / len(vals), 4)
    value = iv.get("value") if isinstance(iv.get("value"), dict) else None
    if value and value.get("value") not in (None, ""):
        try:
            return _scale_metric(float(value["value"]), value.get("unit"))
        except (TypeError, ValueError):
            return None
    return None


def flatten_api_row(board: str, row: dict[str, Any]) -> dict[str, Any]:
    """Normalize heterogeneous board row shapes into map_rank_row inputs."""
    board_key = normalize_board(board)
    src = row if isinstance(row, dict) else {}

    if board_key == "search":
        cell = src.get("cell_info") if isinstance(src.get("cell_info"), dict) else {}
        product = {}
        if isinstance(cell.get("product"), dict):
            product = cell["product"].get("product") or {}
        shop = {}
        if isinstance(cell.get("shop"), dict):
            shop = cell["shop"].get("shop") or {}
        rank_cell = cell.get("rank") if isinstance(cell.get("rank"), dict) else {}
        rank_iv = (
            rank_cell.get("index_values")
            if isinstance(rank_cell.get("index_values"), dict)
            else {}
        )
        rank_val = rank_iv.get("value") if isinstance(rank_iv.get("value"), dict) else {}
        flat = {
            "product_id": product.get("product_id") or product.get("id"),
            "product_name": product.get("product_name") or product.get("name"),
            "main_image": product.get("product_image") or product.get("image"),
            "shop_name": shop.get("shop_name"),
            "rank": rank_val.get("value"),
            "pay_amt": _cell_range_mid(cell.get("pay_amt")),
            "show_cnt": _cell_range_mid(cell.get("search_show_ucnt")),
            "product_click_cnt": None,
            "pay_cnt": None,
            "deal_cnt": None,
            "product_click_pay_cnt_ratio": None,
            "order_cnt": None,
            "category_path": "",
            "_board": board_key,
            "_api_row": src,
        }
        return flat

    product_info = src.get("product_info") if isinstance(src.get("product_info"), dict) else {}
    shop_info = src.get("shop_info") if isinstance(src.get("shop_info"), dict) else {}
    shop_name = shop_info.get("shop_name")
    if not shop_name and isinstance(product_info.get("shop_list"), list) and product_info["shop_list"]:
        first_shop = product_info["shop_list"][0]
        if isinstance(first_shop, dict):
            shop_name = first_shop.get("shop_name")

    pay_amt = _mid_value_range(src.get("pay_amt"))
    if pay_amt is None:
        pay_amt = _mid_value_range(src.get("new_pay_amt"))

    click_pay = _mid_value_range(src.get("click_pay_rate"))
    if click_pay is None:
        click_pay = _mid_value_range(src.get("product_click_pay_cnt_ratio"))

    deal = _mid_value_range(src.get("pay_combo_cnt"))
    orders = _mid_value_range(src.get("pay_cnt"))
    show = _mid_value_range(src.get("show_cnt"))
    if show is None:
        show = _mid_value_range(src.get("product_show_cnt"))

    flat = {
        "product_id": product_info.get("id") or product_info.get("product_id") or src.get("product_id"),
        "product_name": product_info.get("name") or product_info.get("product_name"),
        "main_image": (
            product_info.get("image")
            or product_info.get("image_url")
            or product_info.get("product_image")
        ),
        "shop_name": shop_name,
        "rank": src.get("rank") or product_info.get("rank"),
        "pay_amt": pay_amt,
        "product_click_cnt": _mid_value_range(src.get("product_click_cnt")),
        "pay_cnt": orders if orders is not None else deal,
        "deal_cnt": deal,
        "product_click_pay_cnt_ratio": click_pay,
        "show_cnt": show,
        # 成交订单数：接口有 pay_cnt 用 pay_cnt；昨日商品卡常返回空 {}，用成交件数兜底便于对照
        "order_cnt": orders if orders is not None else deal,
        "category_path": str(product_info.get("leaf_category_id") or ""),
        "_board": board_key,
        "_api_row": src,
        "_pay_cnt_empty": orders is None,
        "_show_cnt_empty": show is None,
    }
    return flat


def _report_day_for(date_window: str, *, date_type: int | None = None) -> str:
    today = datetime.now(SHANGHAI).date()
    yesterday = today - timedelta(days=1)
    dw = normalize_date_window(date_window)
    if date_type == 1 or dw == "today":
        # realtime window → calendar today; search fallback to 20 still labels today
        if date_type == 20 and dw == "today":
            return yesterday.strftime("%Y-%m-%d")
        return today.strftime("%Y-%m-%d")
    return yesterday.strftime("%Y-%m-%d")


def _date_bounds(date_type: int) -> tuple[str, str, str]:
    today = datetime.now(SHANGHAI).date()
    yesterday = today - timedelta(days=1)
    if int(date_type) == 1:
        begin = end = today
        report = today
    elif int(date_type) == 20:
        begin = end = yesterday
        report = yesterday
    else:
        begin = end = today
        report = today
    fmt = lambda d: d.strftime("%Y/%m/%d 00:00:00")
    return fmt(begin), fmt(end), report.strftime("%Y-%m-%d")


def _resolve_date_type(board: str, date_window: str) -> int:
    board_key = normalize_board(board)
    dw = normalize_date_window(date_window)
    if board_key == "search":
        return int(SEARCH_DATE_WINDOW_DATE_TYPE.get(dw) or 20)
    return int(DATE_WINDOW_DATE_TYPE.get(dw) or (1 if dw == "today" else 20))


def _page_fetch_json(page, path: str, params: dict[str, Any]) -> dict[str, Any]:
    result = page.evaluate(
        """async ({ path, params }) => {
          const q = new URLSearchParams();
          Object.entries(params || {}).forEach(([k, v]) => {
            if (v === undefined || v === null) return;
            q.set(k, String(v));
          });
          const r = await fetch(path + '?' + q.toString(), { credentials: 'include' });
          let body = null;
          try { body = await r.json(); } catch (e) { body = { parse_error: String(e) }; }
          return { status: r.status, body };
        }""",
        {"path": path, "params": params},
    )
    if not isinstance(result, dict):
        raise RuntimeError("DY_COMPASS_RANK_SOURCE_UNAVAILABLE: 罗盘商品榜接口返回异常")
    if int(result.get("status") or 0) >= 400:
        raise RuntimeError(
            f"DY_COMPASS_RANK_SOURCE_UNAVAILABLE: HTTP {result.get('status')}"
        )
    body = result.get("body")
    if not isinstance(body, dict):
        raise RuntimeError("DY_COMPASS_RANK_SOURCE_UNAVAILABLE: 罗盘商品榜非 JSON 对象")
    st = body.get("st", body.get("code"))
    if st not in (0, "0", None, ""):
        raise RuntimeError(
            f"DY_COMPASS_RANK_SOURCE_UNAVAILABLE: st={st} msg={body.get('msg') or body.get('message')}"
        )
    return body


def _extract_rows(board: str, body: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    board_key = normalize_board(board)
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    meta_extra: dict[str, Any] = {}
    if board_key == "search":
        module = ((data.get("module_data") or {}).get("search_product_rank") or {})
        table = module.get("compass_general_table_value") if isinstance(module, dict) else {}
        rows = table.get("data") if isinstance(table, dict) else None
        if not isinstance(rows, list):
            rows = []
        return [r for r in rows if isinstance(r, dict)], meta_extra
    if board_key == "product_card":
        rows = data.get("card_list")
        if isinstance(data.get("page_result"), dict):
            meta_extra["page_result"] = data["page_result"]
        if not isinstance(rows, list):
            rows = []
        return [r for r in rows if isinstance(r, dict)], meta_extra
    # total
    rows = data.get("data_result")
    if isinstance(data.get("page_result"), dict):
        meta_extra["page_result"] = data["page_result"]
    if isinstance(data.get("main_industry"), dict):
        meta_extra["main_industry"] = data["main_industry"]
    if not isinstance(rows, list):
        rows = []
    return [r for r in rows if isinstance(r, dict)], meta_extra


def _build_params(
    board: str,
    *,
    date_type: int,
    begin_date: str,
    end_date: str,
    industry_id: str,
    category_id: str,
    page_no: int,
    page_size: int,
) -> dict[str, str]:
    board_key = normalize_board(board)
    common = {
        "begin_date": begin_date,
        "end_date": end_date,
        "date_type": str(date_type),
        "industry_id": str(industry_id or ""),
        "category_id": str(category_id or ""),
        "brand_type": "-1",
        "page_no": str(page_no),
        "page_size": str(page_size),
        "activity_id": "",
        "price_bin": "不限",
    }
    if board_key == "search":
        common.update({"content_type": "0", "source_biz_type": "1"})
    elif board_key == "product_card":
        common.update(
            {
                "sort_field": "pay_amt",
                "is_asc": "false",
                "rank_data_type": "1",
                "top_myshop": "false",
            }
        )
    else:
        common.update({"rank_data_type": "1"})
    return common


def _capture_default_category(page) -> dict[str, str]:
    """Open rank page and learn default industry/category from first rank XHRs.

    Does not interact with the category picker.
    """
    found: dict[str, str] = {"industry_id": "", "category_id": "", "category_name": ""}

    def on_request(req) -> None:
        try:
            u = req.url or ""
            if "product_rank" not in u:
                return
            qs = parse_qs(urlparse(u).query)
            ind = (qs.get("industry_id") or [""])[0]
            cat = (qs.get("category_id") or [""])[0]
            if ind and not found["industry_id"]:
                found["industry_id"] = ind
            if cat and not found["category_id"]:
                found["category_id"] = cat
        except Exception:
            pass

    page.on("request", on_request)
    try:
        page.goto(DOUYIN_COMPASS_RANK_PAGE, wait_until="domcontentloaded", timeout=90_000)
    except Exception as exc:  # noqa: BLE001
        try:
            page.remove_listener("request", on_request)
        except Exception:
            pass
        raise RuntimeError(
            f"DY_COMPASS_RANK_SOURCE_UNAVAILABLE: 无法打开罗盘商品榜: {exc}"
        ) from exc

    deadline = time.time() + 14.0
    nudged = False
    while time.time() < deadline:
        if found["industry_id"] and found["category_id"]:
            break
        if not nudged and time.time() > deadline - 8:
            nudged = True
            for label in ("总榜", "商品卡榜", "搜索榜", "近1天", "实时"):
                try:
                    loc = page.get_by_text(label, exact=True).first
                    if loc.is_visible(timeout=800):
                        loc.click(timeout=2000)
                        time.sleep(1.5)
                        break
                except Exception:
                    continue
        time.sleep(0.35)
    try:
        page.remove_listener("request", on_request)
    except Exception:
        pass
    return found


def fetch_board_slice(
    page,
    *,
    board: str,
    date_window: str,
    limit: int = 200,
    industry_id: str = "",
    category_id: str = "",
    category_name: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch one board × date_window slice (Top ``limit``) via in-page Compass API."""
    board_key = normalize_board(board)
    dw = normalize_date_window(date_window)
    api = BOARD_RANK_API.get(board_key)
    if not api:
        raise RuntimeError(f"DY_COMPASS_RANK_SOURCE_UNAVAILABLE: 未知榜单 {board}")

    date_type = _resolve_date_type(board_key, dw)
    begin_date, end_date, report_day = _date_bounds(date_type)
    # Preserve business report_day semantics for search/today fallback.
    if board_key == "search" and dw == "today":
        report_day = _report_day_for(dw, date_type=date_type)

    need = max(1, min(200, int(limit or 200)))
    # Compass rank APIs paginate with page_size=10 (probed); requesting 50 returns ≤10
    # and the old "len(rows) < page_size" stop cut off after page 1.
    page_size = 10
    collected: list[dict[str, Any]] = []
    last_extra: dict[str, Any] = {}

    max_pages = (need + page_size - 1) // page_size + 2
    for page_no in range(1, max_pages + 1):
        if len(collected) >= need:
            break
        params = _build_params(
            board_key,
            date_type=date_type,
            begin_date=begin_date,
            end_date=end_date,
            industry_id=industry_id,
            category_id=category_id,
            page_no=page_no,
            page_size=page_size,
        )
        try:
            body = _page_fetch_json(page, api, params)
        except Exception as exc:  # noqa: BLE001
            if page_no == 1:
                raise
            print(f"[DouyinCompassRank] {board_key}/{dw} page={page_no} stop: {exc}", flush=True)
            break
        rows, extra = _extract_rows(board_key, body)
        last_extra = extra or last_extra
        if not rows:
            break
        collected.extend(rows)
        pr = extra.get("page_result") if isinstance(extra, dict) else None
        total_hint = None
        if isinstance(pr, dict):
            total_hint = pr.get("total")
        if total_hint is not None and len(collected) >= int(total_hint or 0):
            break
        if len(rows) < page_size:
            break

    collected = collected[:need]
    products: list[dict[str, Any]] = []
    for idx, row in enumerate(collected, start=1):
        flat = flatten_api_row(board_key, row)
        mapped = map_rank_row(flat, idx)
        # Keep full API row in raw for ingest.
        mapped["raw"] = row
        if mapped.get("product_id"):
            products.append(mapped)

    cat_name = category_name or ""
    main_ind = last_extra.get("main_industry") if isinstance(last_extra, dict) else None
    if not cat_name and isinstance(main_ind, dict):
        cat_name = str(main_ind.get("name") or main_ind.get("industry_name") or "")

    meta = {
        "board": board_key,
        "date_window": dw,
        "date_type": date_type,
        "report_day": report_day,
        "category_id": category_id,
        "category_name": cat_name or (category_id or "默认类目"),
        "industry_id": industry_id,
        "is_default_category": True,
        "source_url": DOUYIN_COMPASS_RANK_PAGE,
        "total_hint": (last_extra.get("page_result") or {}).get("total")
        if isinstance(last_extra.get("page_result"), dict)
        else len(products),
    }
    print(
        f"[DouyinCompassRank] {board_key}/{dw} date_type={date_type} "
        f"products={len(products)} category={meta['category_id']}",
        flush=True,
    )
    return products, meta


def run_compass_product_rank_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    """Sync 3 boards × 2 date windows (Top 200 each) into Java ingest."""
    from agent.douyin_tasks import (
        _close_pw,
        _launch,
        _looks_logged_in,
        _resolve_store_id,
        _wait_until_logged_in,
    )

    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    job_id = str(payload.get("job_id") or "")
    store_id = str(payload.get("store_id") or "").strip()

    if not DOUYIN_COMPASS_RANK_XHR_READY:
        raise RuntimeError("DY_COMPASS_RANK_SOURCE_UNAVAILABLE: 罗盘商品榜接口尚未就绪")

    store_id = _resolve_store_id(client, tenant_id, store_id)
    if not store_id:
        store_id = "default"

    boards = ("search", "product_card", "total")
    windows = ("today", "yesterday")
    slice_results: list[dict[str, Any]] = []
    total_products = 0

    pw = context = page = None
    try:
        pw, context, page = _launch(
            tenant_id,
            headless=False,
            force_navigate=True,
            store_id=store_id,
        )
        if not _looks_logged_in(page, context):
            logged_in, page = _wait_until_logged_in(
                page,
                context,
                timeout_seconds=300,
                label="compass_product_rank_sync",
            )
            if not logged_in:
                raise RuntimeError("DY_NOT_LOGGED_IN: 抖音商家后台未登录，请打开登录窗口完成登录")

        cats = _capture_default_category(page)
        industry_id = cats.get("industry_id") or ""
        category_id = cats.get("category_id") or ""
        if not industry_id or not category_id:
            raise RuntimeError(
                "DY_COMPASS_RANK_SOURCE_UNAVAILABLE: 未能读取默认类目 industry_id/category_id"
            )

        any_ok = False
        for board in boards:
            for date_window in windows:
                products, meta = fetch_board_slice(
                    page,
                    board=board,
                    date_window=date_window,
                    limit=200,
                    industry_id=industry_id,
                    category_id=category_id,
                    category_name=cats.get("category_name") or "",
                )
                if not products:
                    print(
                        f"[DouyinCompassRank] empty slice {board}/{date_window}",
                        flush=True,
                    )
                else:
                    any_ok = True
                # Top50: fill 曝光人数 / 成交订单数 from compete product overview XHR
                enrich_stats = enrich_products_with_compete_core_index(
                    page,
                    products,
                    date_window=date_window,
                    top_n=COMPETE_ENRICH_TOP_N,
                )
                ingest_body = {
                    "job_id": job_id,
                    "store_id": store_id,
                    "board": board,
                    "date_window": date_window,
                    "report_day": meta.get("report_day"),
                    "category_id": meta.get("category_id"),
                    "category_name": meta.get("category_name"),
                    "is_default_category": True,
                    "source_url": meta.get("source_url") or DOUYIN_COMPASS_RANK_PAGE,
                    "products": products[:200],
                    "message": (
                        f"已同步罗盘商品榜 {board}/{date_window} Top{len(products)}"
                        f"（明细补齐 show={enrich_stats.get('filled_show', 0)} "
                        f"order={enrich_stats.get('filled_order', 0)}）"
                    ),
                }
                client.ingest_douyin_compass_product_rank(ingest_body)
                total_products += len(products)
                slice_results.append(
                    {
                        "board": board,
                        "date_window": date_window,
                        "count": len(products),
                        "report_day": meta.get("report_day"),
                        "date_type": meta.get("date_type"),
                        "enrich": enrich_stats,
                    }
                )
        if not any_ok:
            raise RuntimeError("DY_COMPASS_RANK_SOURCE_UNAVAILABLE: 六个切片均无数据")
    finally:
        _close_pw(pw, context)

    message = (
        f"已同步罗盘商品榜 6 组，合计 {total_products} 条"
        f"（类目 {category_id}）"
    )
    return {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "scope": "compass_product_rank",
        "orders_count": 0,
        "products_count": total_products,
        "issues_count": 0,
        "partial": False,
        "message": message,
        "synced_at": datetime.now(SHANGHAI).isoformat(),
        "source_url": DOUYIN_COMPASS_RANK_PAGE,
        "category_id": category_id,
        "industry_id": industry_id,
        "slices": slice_results,
        "count": total_products,
    }
