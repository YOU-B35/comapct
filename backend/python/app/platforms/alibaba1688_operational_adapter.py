"""1688 operational crawl adapter."""
from __future__ import annotations

from typing import Any

from app.crawler.alibaba1688_crawler import crawl_purchase_orders, login_probe
from app.ingest_alibaba1688 import upsert_purchase_orders
from app.platforms.operational_base import PlatformOperationalAdapter


class Alibaba1688OperationalAdapter(PlatformOperationalAdapter):
    platform = "1688"

    def crawl_and_ingest(
        self,
        *,
        tenant_id: int,
        report_day: str | None = None,
        use_seed: bool = False,
        scope: str = "all",
    ) -> dict[str, Any]:
        if use_seed:
            raise RuntimeError("1688 seed mode disabled")
        scope_key = (scope or "sync").strip().lower()
        if scope_key in ("login_probe",):
            result = login_probe(tenant_id=tenant_id, headed=False)
            return {
                "platform": self.platform,
                "tenant_id": tenant_id,
                "report_time": report_day,
                "rows": 0,
                **result,
            }

        # crawl / sync / all / operational → sync purchases
        result = crawl_purchase_orders(tenant_id=tenant_id, headed=False)
        rows = result.get("rows") or []
        if isinstance(rows, list) and rows:
            written = upsert_purchase_orders(tenant_id, rows)
        else:
            written = 0
        return {
            "platform": self.platform,
            "tenant_id": tenant_id,
            "report_time": report_day,
            "rows": written,
            "status": result.get("status") or "success",
            "message": result.get("message") or "",
        }
