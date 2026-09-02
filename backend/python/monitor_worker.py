#!/usr/bin/env python3
"""Consume pending monitor jobs and persist monitor snapshots."""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.db import connect, init_schema, seed_users
from app.monitor_db import init_monitor_result_schema, init_monitor_schema
from app.monitor_schedule_enqueuer import enqueue_due_jobs
from app.monitor_worker_service import process_next_pending_job
from app.platforms.alibaba1688_monitor_adapter import Alibaba1688MonitorAdapter
from app.platforms.pdd_monitor_adapter import PddMonitorAdapter
from app.platforms.temu_monitor_adapter import TemuMonitorAdapter


def process_one_job(*, worker_id: str, report_root: Path) -> dict[str, Any] | None:
    conn = connect()
    try:
        init_schema(conn)
        seed_users(conn)
        init_monitor_schema(conn)
        init_monitor_result_schema(conn)
        enqueue_due_jobs(conn)
        return process_next_pending_job(
            conn,
            adapters={
                "temu": TemuMonitorAdapter(),
                "1688": Alibaba1688MonitorAdapter(),
                "pdd": PddMonitorAdapter(),
            },
            report_root=report_root,
            worker_id=worker_id,
        )
    finally:
        conn.close()


def run_worker_loop(
    *,
    process_once: Callable[[], dict[str, Any] | None],
    sleep_fn: Callable[[float], None] = time.sleep,
    interval_seconds: float = 30.0,
    max_idle_cycles: int | None = None,
    on_result: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    idle_cycles = 0
    while True:
        result = process_once() or {"status": "idle"}
        results.append(result)
        if on_result:
            on_result(result)

        if result.get("status") == "idle":
            idle_cycles += 1
        else:
            idle_cycles = 0

        if max_idle_cycles is not None and idle_cycles >= max_idle_cycles:
            break

        sleep_fn(interval_seconds)
    return results


def emit_result(result: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False), flush=True)
    elif result.get("status") == "idle":
        print("status=idle", flush=True)
    else:
        print(
            f"job_id={result['job_id']} status={result['status']} snapshot_id={result['snapshot_id']} "
            f"products={result['product_count']}",
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor worker")
    parser.add_argument("--once", action="store_true", help="Process at most one pending job")
    parser.add_argument("--loop", action="store_true", help="Continuously poll pending monitor jobs")
    parser.add_argument("--interval-seconds", type=float, default=30.0, help="Sleep seconds between loop polls")
    parser.add_argument("--max-idle-cycles", type=int, default=None, help="Stop loop after this many idle polls")
    parser.add_argument("--worker-id", default="monitor-worker", help="Worker identifier")
    parser.add_argument("--report-root", default="reports", help="Directory for generated reports")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report_root = Path(__file__).resolve().parent / args.report_root
    try:
        if args.loop:
            run_worker_loop(
                process_once=lambda: process_one_job(worker_id=args.worker_id, report_root=report_root),
                interval_seconds=args.interval_seconds,
                max_idle_cycles=args.max_idle_cycles,
                on_result=lambda item: emit_result(item, json_output=args.json),
            )
            return
        result = process_one_job(worker_id=args.worker_id, report_root=report_root) or {"status": "idle"}
    except Exception as exc:
        print(f"Monitor worker failed: {exc}", file=sys.stderr)
        sys.exit(1)

    emit_result(result, json_output=args.json)


if __name__ == "__main__":
    main()
