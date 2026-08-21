"""1688 同行爆款爬取任务：以本店销量 Top 商品为种子抓同款/相似款并入库。"""
from __future__ import annotations

import re
import sqlite3
import time
import json
from pathlib import Path
from typing import Any

from agent.alibaba1688_order_tasks import _mtop
from agent.alibaba1688_tasks import _close, _launch, _looks_logged_in

DB = Path(r"D:\YOTO-SASS\SaaS-HZ_WEB_Demo\backend\data\crosshub.db")
MMGA = "mtop.1688.mmga.offerdetail.service"
SEED_LIMIT = 40
MAX_RESULT = 50


def parse_sales(text_value: str | None) -> int:
    text = str(text_value or "")
    m = re.search(r"([\d.]+)\s*(万)?\+?件", text)
    if not m:
        return 0
    num = float(m.group(1))
    if m.group(2):
        num *= 10000
    return int(num)


def peer_suggestion(sales: int) -> str:
    if sales >= 100000:
        return "现象级爆款，建议重点对标价格与卖点"
    if sales >= 10000:
        return "高销量爆款，建议重点追踪"
    if sales >= 1000:
        return "热销款，建议持续关注"
    if sales >= 100:
        return "有起量迹象，建议观察趋势"
    return "销量一般，建议结合价格与质量评估"


def seed_offer_ids(limit: int = SEED_LIMIT, store_id: str = "default") -> list[str]:
    c = sqlite3.connect(str(DB))
    try:
        is_default = store_id in ("default", "", None)
        if is_default:
            # 默认店铺不按 store_id 过滤：历史数据可能挂在账号 UUID 或 default 下
            rows = c.execute(
                """
                SELECT i.offer_id
                FROM alibaba1688_order_item i
                JOIN alibaba1688_order o ON o.tenant_id = i.tenant_id
                  AND o.store_id = i.store_id AND o.order_no = i.order_no
                WHERE i.offer_id <> '' AND o.paid_at <> ''
                GROUP BY i.offer_id
                ORDER BY SUM(CAST(i.quantity AS REAL)) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            own = {
                str(r[0])
                for r in c.execute(
                    "SELECT offer_id FROM alibaba1688_product"
                ).fetchall()
            }
        else:
            rows = c.execute(
                """
                SELECT i.offer_id
                FROM alibaba1688_order_item i
                JOIN alibaba1688_order o ON o.tenant_id = i.tenant_id
                  AND o.store_id = i.store_id AND o.order_no = i.order_no
                WHERE i.offer_id <> '' AND o.paid_at <> '' AND i.store_id = ?
                GROUP BY i.offer_id
                ORDER BY SUM(CAST(i.quantity AS REAL)) DESC
                LIMIT ?
                """,
                (store_id, limit),
            ).fetchall()
            own = {
                str(r[0])
                for r in c.execute(
                    "SELECT offer_id FROM alibaba1688_product WHERE store_id = ?",
                    (store_id,),
                ).fetchall()
            }
        return [str(r[0]) for r in rows if str(r[0]) in own]
    finally:
        c.close()


def _parse_compare(resp: dict[str, Any]) -> list[dict[str, Any]]:
    data = resp.get("data") or {}
    out = []
    for item in data.get("offerList") or []:
        if not isinstance(item, dict) or item.get("isCurrentOffer"):
            continue
        out.append(
            {
                "offer_id": str(item.get("offerId") or ""),
                "title": str(item.get("title") or ""),
                "price": str(item.get("price") or ""),
                "sale_text": str(item.get("saleText") or ""),
                "sales": parse_sales(item.get("saleText")),
                "offer_url": str(item.get("offerUrl") or ""),
                "image_url": str(item.get("imageUrl") or ""),
                "shop_name": "",
            }
        )
    return out


def _parse_similar(resp: dict[str, Any]) -> dict[str, dict[str, Any]]:
    data = (resp.get("data") or {}).get("data") or {}
    out: dict[str, dict[str, Any]] = {}
    for item in data.get("itemList") or []:
        if not isinstance(item, dict):
            continue
        oid = str(item.get("itemId") or "")
        if not oid:
            continue
        out[oid] = {
            "offer_id": oid,
            "title": "",
            "price": str(item.get("price") or ""),
            "sale_text": str(item.get("salesCount") or ""),
            "sales": parse_sales(item.get("salesCount")),
            "offer_url": str(item.get("linkUrl") or ""),
            "image_url": str(item.get("imageUrl") or ""),
            "shop_name": str(item.get("shopName") or ""),
        }
    return out


def _extract_detail_enrichment(responses: list[str]) -> dict[str, str]:
    """从详情页响应中提取店铺名与质量分（复购率/品质达标率）。"""
    shop_name = ""
    quality_parts: list[str] = []
    for text in responses:
        try:
            body = text
            if body.lstrip().startswith("mtopjsonp"):
                body = body[body.find("(") + 1: body.rfind(")")]
            payload = json.loads(body)
        except Exception:
            continue
        data = payload.get("data") or {}
        model = data.get("model") if isinstance(data, dict) else None
        if isinstance(model, dict):
            if model.get("shopName"):
                shop_name = str(model["shopName"])
            for row in model.get("shopData") or []:
                if isinstance(row, dict) and str(row.get("dataKey") or "") in ("品质达标率", "店铺回头率"):
                    quality_parts.append(f"{row['dataKey']}{row.get('dataValue', '')}")
        inner = (data.get("data") or {}) if isinstance(data, dict) else {}
        if isinstance(inner, dict):
            for block in inner.get("data") or []:
                if isinstance(block, dict) and block.get("providerType") == "RebuyRateDataProvider":
                    m = re.search(r"复购率\s*([\d.]+%)", str(block.get("text") or ""))
                    if m:
                        quality_parts.append(f"复购{m.group(1)}")
    return {"shop_name": shop_name, "quality_score": " · ".join(dict.fromkeys(quality_parts))}


def _merge(merged: dict[str, dict[str, Any]], item: dict[str, Any], enrich_only: bool = False) -> None:
    oid = item["offer_id"]
    if not oid:
        return
    existing = merged.get(oid)
    if existing is None:
        merged[oid] = dict(item)
        return
    if enrich_only:
        if not existing.get("shop_name") and item.get("shop_name"):
            existing["shop_name"] = item["shop_name"]
        if existing.get("sales", 0) < item.get("sales", 0):
            existing["sales"] = item["sales"]
            if item.get("sale_text"):
                existing["sale_text"] = item["sale_text"]
        if not existing.get("price") and item.get("price"):
            existing["price"] = item["price"]
    else:
        if item.get("sales", 0) > existing.get("sales", 0):
            existing["sales"] = item["sales"]
            existing["sale_text"] = item.get("sale_text") or existing.get("sale_text", "")
        for key in ("title", "price", "offer_url", "image_url"):
            if not existing.get(key) and item.get(key):
                existing[key] = item[key]


def run_peer_bestsellers_sync(client, task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload") or {}
    tenant_id = int(payload.get("tenant_id") or 0)
    store_id = str(payload.get("store_id") or "").strip() or "default"
    seeds = seed_offer_ids(SEED_LIMIT, store_id)
    if not seeds:
        return {"ingested": 0, "scanned": 0, "message": "暂无本店销量数据，先同步订单"}
    started = time.monotonic()
    pw = context = page = None
    merged: dict[str, dict[str, Any]] = {}
    top: list[dict[str, Any]] = []
    try:
        pw, context, page = _launch(
            tenant_id,
            headless=True,
            goto="https://work.1688.com/",
            store_id=store_id,
        )
        if not _looks_logged_in(page, context):
            raise RuntimeError("A1688_NOT_LOGGED_IN: 1688 未登录或登录已失效，请重新打开登录窗口")
        page.wait_for_timeout(5000)
        for offer_id in seeds:
            calls = (
                (
                    "compare",
                    {"mmgaRequest": {"serviceName": "compareOfferSelectListService", "offerId": int(offer_id), "queryType": "similar", "querySource": "PC", "needSort": True}},
                ),
                (
                    "similar",
                    {"mmgaRequest": {"serviceName": "offerSimilarSameService", "offerId": int(offer_id), "querySource": "PC", "needSort": True}},
                ),
            )
            for label, data in calls:
                try:
                    resp = _mtop(page, MMGA, data)
                    if label == "compare":
                        for item in _parse_compare(resp):
                            _merge(merged, item)
                    else:
                        for oid, item in _parse_similar(resp).items():
                            _merge(merged, item, enrich_only=True)
                except Exception as exc:
                    print(f"[1688Peer] seed {offer_id} {label} EXC {str(exc)[:140]}", flush=True)
                time.sleep(0.5)

        own_ids = _own_offer_ids(store_id)
        items = [v for v in merged.values() if v["offer_id"] not in own_ids and v["sales"] > 0]
        items.sort(key=lambda x: x["sales"], reverse=True)
        top = items[:MAX_RESULT]
        for item in top:
            item["suggestion"] = peer_suggestion(item["sales"])
        # 详情富化：用「同款对比」自种子补全缺失标题（currentOffer 固定返回标题）
        for item in [it for it in top if not it.get("title")]:
            try:
                resp = _mtop(
                    page,
                    MMGA,
                    {"mmgaRequest": {"serviceName": "compareOfferSelectListService", "offerId": int(item["offer_id"]), "queryType": "similar", "querySource": "PC", "needSort": True}},
                )
                cur = (resp.get("data") or {}).get("currentOffer") or {}
                if cur.get("title"):
                    item["title"] = str(cur["title"])
            except Exception as exc:
                print(f"[1688Peer] title enrich {item['offer_id']} EXC {str(exc)[:120]}", flush=True)
            time.sleep(0.5)
        # 详情富化：打开商品详情页，捕获店铺名与质量分（页面自动带上下文调用）
        to_enrich = [it for it in top if not it.get("shop_name") or not it.get("quality_score")]
        for item in to_enrich:
            responses: list[str] = []

            def on_response(resp) -> None:
                try:
                    url = resp.url or ""
                    if "moga.pc.shopcard" in url or "mmga.offerdetail.service" in url:
                        text = resp.text()
                        if text and ("shopName" in text or "RebuyRate" in text or "shopName" in text):
                            responses.append(text)
                except Exception:
                    pass

            page.on("response", on_response)
            try:
                page.goto(f"https://detail.1688.com/offer/{item['offer_id']}.html", wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_timeout(6000)
            except Exception as exc:
                print(f"[1688Peer] detail {item['offer_id']} EXC {str(exc)[:120]}", flush=True)
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass
            enriched = _extract_detail_enrichment(responses)
            if enriched["shop_name"]:
                item["shop_name"] = enriched["shop_name"]
            if enriched["quality_score"]:
                item["quality_score"] = enriched["quality_score"]
            time.sleep(0.5)
    finally:
        _close(pw, context)

    client.ingest_1688_peer_bestsellers(
        {"tenant_id": tenant_id, "store_id": store_id, "items": top}
    )
    return {
        "ingested": len(top),
        "scanned": len(merged),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }


def _own_offer_ids(store_id: str = "default") -> set[str]:
    c = sqlite3.connect(str(DB))
    try:
        return {
            str(r[0])
            for r in c.execute(
                "SELECT offer_id FROM alibaba1688_product WHERE store_id = ?",
                (store_id,),
            ).fetchall()
        }
    finally:
        c.close()
