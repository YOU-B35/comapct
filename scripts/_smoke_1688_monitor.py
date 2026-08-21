"""Smoke: collect the three seed 1688 shops once and print a summary."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "python"))

from app.platforms.alibaba1688_shop_collector import crawl_shop  # noqa: E402

SEEDS = [
    {"label": "寻渔记", "url": "https://shop17682i6w5i484.1688.com", "pinned": ["867473865842"]},
    {"label": "东博瑞", "url": "https://shop16yx1905b2433.1688.com", "pinned": ["930671411701"]},
    {"label": "酷诺", "url": "https://shop45996540o0794.1688.com", "pinned": ["979632972917"]},
]


def main() -> int:
    for seed in SEEDS:
        target = {
            "target_url": seed["url"],
            "crawl_strategy": "1688_shop_topn",
            "config_json": json.dumps({"top_n": 20, "pinned_offer_ids": seed["pinned"]}, ensure_ascii=False),
        }
        payload = crawl_shop(tenant_id=5, target=target, max_products=20)
        print(seed["label"], "products:", len(payload["products"]), "member:", payload["meta"]["member_id"], flush=True)
        for p in payload["products"][:5]:
            print(
                "  ",
                p.get("rank"),
                p.get("offer_id"),
                str(p.get("title"))[:28],
                p.get("price"),
                p.get("sale_text"),
                p.get("total_sales"),
                p.get("rebuy_rate"),
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
