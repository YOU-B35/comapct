#!/usr/bin/env python3
"""入口：python crawl.py --tenant-id 1 [--date YYYY-MM-DD] [--seed]"""
from __future__ import annotations

import argparse
import sys

from app.config import resolve_tenant_id
from app.ingest import run_ingest


def main() -> None:
    parser = argparse.ArgumentParser(description="Temu 爬虫入库")
    parser.add_argument("--tenant-id", type=int, help="租户 ID（必填，或设置 TENANT_ID）")
    parser.add_argument("--date", help="上报日期 YYYY-MM-DD，默认今天")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="已禁用：请完成 Temu 登录后使用 live 爬取",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="成功时向 stdout 输出单行 JSON（供 Java 解析）",
    )
    args = parser.parse_args()

    try:
        tenant_id = resolve_tenant_id(args.tenant_id)
    except ValueError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(2)

    if args.seed:
        print("错误: 种子数据模式已关闭，请完成 Temu 登录后使用真实爬取", file=sys.stderr)
        sys.exit(1)

    try:
        result = run_ingest(args.date, use_seed=args.seed, tenant_id=tenant_id)
    except Exception as exc:
        msg = str(exc)
        if any(token in msg for token in ("未登录", "登录已过期", "登录窗口")):
            try:
                from app.browser.profile_lock import clear_session_cache

                clear_session_cache(tenant_id)
            except Exception:
                pass
        print(f"爬取失败: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        import json

        print(
            json.dumps(
                {
                    "tenant_id": tenant_id,
                    "report_time": result["report_time"],
                    "shops": result["shops"],
                    "rows": result["rows"],
                },
                ensure_ascii=False,
            )
        )
    else:
        print(
            f"tenant_id={tenant_id} report_time={result['report_time']} "
            f"shops={result['shops']} rows={result['rows']}"
        )


if __name__ == "__main__":
    main()
