#!/usr/bin/env python3
"""多平台运营爬取统一入口：python operational_crawl.py --platform temu|aliexpress --tenant-id 1"""
from __future__ import annotations

import argparse
import json
import sys

from app.config import resolve_tenant_id
from app.operational.registry import get_operational_adapter, supported_platforms


def main() -> None:
    parser = argparse.ArgumentParser(description="多平台运营数据爬取入库")
    parser.add_argument("--platform", required=True, choices=supported_platforms())
    parser.add_argument("--tenant-id", type=int, help="租户 ID（必填，或设置 TENANT_ID）")
    parser.add_argument("--date", help="上报日期 YYYY-MM-DD，默认今天")
    parser.add_argument(
        "--scope",
        default="all",
        choices=["all", "orders", "violations", "operational", "login_probe", "sync"],
        help="抓取范围；1688 使用 login_probe|sync；AliExpress 使用 orders|violations|all",
    )
    parser.add_argument("--seed", action="store_true", help="已禁用")
    parser.add_argument("--json", action="store_true", help="成功时输出单行 JSON")
    args = parser.parse_args()

    try:
        tenant_id = resolve_tenant_id(args.tenant_id)
    except ValueError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(2)

    adapter = get_operational_adapter(args.platform)
    try:
        result = adapter.crawl_and_ingest(
            tenant_id=tenant_id,
            report_day=args.date,
            use_seed=args.seed,
            scope=args.scope,
        )
    except Exception as exc:
        print(f"爬取失败: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(
            f"platform={result.get('platform')} tenant_id={result.get('tenant_id')} "
            f"report_time={result.get('report_time')} shops={result.get('shops')} "
            f"rows={result.get('rows', 0)} orders={result.get('orders', 0)} "
            f"violations={result.get('violations', 0)} products={result.get('products', 0)}"
        )


if __name__ == "__main__":
    main()
