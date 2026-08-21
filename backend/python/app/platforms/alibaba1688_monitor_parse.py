"""Pure parsers for 1688 shop monitor responses (no browser/DB)."""
from __future__ import annotations

import json
import re
from typing import Any

from app.platforms.alibaba1688_monitor_utils import parse_sales_text


def unwrap_jsonp(text: str) -> str:
    body = str(text or "").strip()
    if body.startswith("mtopjsonp"):
        start = body.find("(")
        end = body.rfind(")")
        if start >= 0 and end > start:
            body = body[start + 1 : end]
    return body


def _json(text: str) -> dict[str, Any]:
    return json.loads(unwrap_jsonp(text))


def parse_shop_list_response(text: str) -> dict[str, Any]:
    payload = _json(text)
    data = payload.get("data") or {}
    appdata = data.get("appdata") or {}
    member_id = str(appdata.get("memberId") or "")
    offers: list[dict[str, Any]] = []
    if str(appdata.get("sortType")) == "tradenumdown":
        for idx, item in enumerate(data.get("offerModuleList") or [], start=1):
            if not isinstance(item, dict):
                continue
            oid = str(item.get("id") or "")
            if not oid or oid == "0":
                continue
            offers.append(parse_list_item(item, rank=idx))
    return {
        "member_id": member_id,
        "offers": offers,
        "total_count": str(data.get("totalCount") or ""),
    }


def parse_list_item(item: dict, *, rank: int) -> dict[str, Any]:
    vague = str(item.get("vagueSaleQuantity") or "")
    rebuy = ""
    for p in item.get("offerPointModelList") or []:
        if isinstance(p, dict) and "复购" in str(p.get("pointText") or ""):
            rebuy = str(p.get("pointText") or "")
            break
    url = str(item.get("offerDetailUrl") or "")
    if url.startswith("//"):
        url = "https:" + url
    price_range = _price_range(item)
    return {
        "offer_id": str(item.get("id") or ""),
        "title": str(item.get("subject") or ""),
        "price": str(item.get("offerPrice") or ""),
        "price_range": price_range,
        "moq": str(item.get("quantityBegin") or ""),
        "good_rate": str(item.get("goodRates") or ""),
        "sale_text": vague,
        "total_sales": parse_sales_text(vague),
        "rank": rank,
        "listed_at": str(item.get("gmtCreate") or "")[:10],
        "url": url,
        "image_url": _first_image(item.get("offerImages")),
        "status": str(item.get("status") or ""),
        "expired": str(item.get("expired") or "").lower() == "true",
        "rebuy_rate": rebuy,
        "raw_json": json.dumps(item, ensure_ascii=False),
    }


def parse_shopcard_response(text: str) -> dict[str, Any]:
    payload = _json(text)
    model = (payload.get("data") or {}).get("model") or {}
    if not model.get("shopName"):
        return {}
    fans = 0
    fav = str(((model.get("shopButton") or {}).get("fuzzyFavCount")) or "")
    m = re.search(r"([\d.]+)\s*([kK万])?", fav)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        if unit and unit.lower() == "k":
            num *= 1000
        elif unit == "万":
            num *= 10000
        fans = int(num)
    shop_data = {}
    for sd in model.get("shopData") or []:
        if isinstance(sd, dict):
            shop_data[str(sd.get("dataKey") or "")] = str(sd.get("dataValue") or "")
    return {
        "shop_name": str(model.get("shopName") or ""),
        "shop_url": str(model.get("shopUrl") or ""),
        "shop_fans": fans,
        "quality_rate": str(model.get("qualitySatisfactionRate") or ""),
        "shop_return_rate": shop_data.get("店铺回头率", ""),
        "delivery_48h_rate": shop_data.get("48小时支揽率", ""),
        "category": str(model.get("mainCategoryName") or ""),
    }


def parse_offer_detail_responses(texts: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {"current": None, "attrs_json": "", "advise": None, "rebuy_rate": ""}
    for text in texts:
        try:
            payload = _json(text)
        except Exception:
            continue
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            continue
        if isinstance(data.get("currentOffer"), dict):
            out["current"] = data["currentOffer"]
        inner = data.get("data")
        if not isinstance(inner, dict):
            continue
        if isinstance(inner.get("offerDecisionAttrs"), list):
            out["attrs_json"] = json.dumps(inner["offerDecisionAttrs"], ensure_ascii=False)
        deeper = inner.get("data")
        if isinstance(deeper, dict) and isinstance(deeper.get("adviseList"), list):
            out["advise"] = deeper["adviseList"]
        elif isinstance(deeper, list):
            for item in deeper:
                if isinstance(item, dict) and "复购" in str(item.get("text") or ""):
                    out["rebuy_rate"] = str(item.get("text") or "")
    return out


def _first_image(value: Any) -> str:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            return str(first.get("originalImageUrl") or first.get("imageUrl") or "")
        return str(first)
    return ""


def _price_range(item: dict[str, Any]) -> str:
    segments = item.get("priceSegments") or []
    prices = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        for key in ("price", "beginPrice", "endPrice"):
            raw = seg.get(key)
            if raw in (None, ""):
                continue
            try:
                prices.append(float(str(raw)))
            except ValueError:
                pass
    if not prices:
        return ""
    return f"{min(prices):.2f}-{max(prices):.2f}"
