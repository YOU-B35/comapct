"""1688 monitor platform adapter."""
from __future__ import annotations

from typing import Any

from app.platforms.alibaba1688_shop_collector import crawl_shop
from app.platforms.base import MonitorPlatformAdapter


class Alibaba1688MonitorAdapter(MonitorPlatformAdapter):
    def crawl_target(self, *, tenant_id: int, target: dict, max_products: int) -> dict[str, Any]:
        payload = crawl_shop(tenant_id=tenant_id, target=target, max_products=max_products)
        products = []
        for row in payload["products"]:
            try:
                price = float(str(row.get("price") or "").replace("¥", ""))
            except ValueError:
                price = 0.0
            products.append(
                {
                    "product_id": str(row["offer_id"]),
                    "product_name": str(row.get("title") or ""),
                    "category": str(row.get("category") or ""),
                    "price": price,
                    "daily_sales": 0,
                    "total_sales": int(row.get("total_sales") or 0),
                    "listed_at": str(row.get("listed_at") or "")[:10],
                    "url": str(row.get("url") or ""),
                    "shop_name": str(row.get("shop_name") or ""),
                    "shop_url": str(row.get("shop_url") or ""),
                    "rank": int(row.get("rank") or 0),
                    "price_range": str(row.get("price_range") or ""),
                    "sale_text": str(row.get("sale_text") or ""),
                    "dropship_7d": str(row.get("dropship_7d") or ""),
                    "dropship_30d": str(row.get("dropship_30d") or ""),
                    "dropship_heat": int(row.get("dropship_heat") or 0),
                    "rebuy_rate": str(row.get("rebuy_rate") or ""),
                    "shop_return_rate": str(row.get("shop_return_rate") or ""),
                    "quality_rate": str(row.get("quality_rate") or ""),
                    "shop_fans": int(row.get("shop_fans") or 0),
                    "attrs_json": str(row.get("attrs_json") or ""),
                    "is_pinned": int(row.get("is_pinned") or 0),
                    "status": str(row.get("status") or ""),
                    "expired": 1 if row.get("expired") else 0,
                    "raw_json": str(row.get("raw_json") or ""),
                }
            )
        return {
            "platform": "1688",
            "snapshot_at": payload["snapshot_at"],
            "products": products,
        }
