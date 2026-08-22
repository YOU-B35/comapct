#!/usr/bin/env python3
"""Migrate server-clock naive UTC timestamps to Asia/Shanghai (+8 hours).

Usage:
  python scripts/migrate_db_utc_to_shanghai.py --db /data/crosshub/data/crosshub.db --dry-run
  python scripts/migrate_db_utc_to_shanghai.py --db /data/crosshub/data/crosshub.db

Only whitelisted "system clock" columns are touched. Platform/business time
columns and any ISO-with-offset values are never modified.
"""

import argparse
import datetime as _dt
import os
import re
import shutil
import sqlite3
import sys

# Columns set by the server clock (Java LocalDateTime.now() / Python datetime.now()).
CLOCK_COLUMNS = {
    "created_at", "updated_at", "started_at", "finished_at", "queued_at",
    "last_heartbeat_at", "bound_at", "last_success_at", "next_retry_at",
    "last_run_at", "next_run_at", "submitted_at", "assigned_at",
    "last_feedback_at", "nudged_at", "joined_at", "read_at",
    "last_analyzed_at", "latest_snapshot_at", "snapshot_at", "synced_at",
}

# Platform/business content times: never migrate, even if the name looks like a clock column.
PLATFORM_COLUMNS = {
    "ordered_at", "paid_at", "refunded_at", "created_platform_at",
    "updated_platform_at", "violated_at", "published_at", "listed_at",
    "join_site_time", "report_time", "data_report_time", "feedback_date",
    "date_window", "snapshot_date", "broadcast_at", "expected_ship_at",
    "expected_arrival_at", "actual_ship_at", "start_at", "end_at",
    "expires_at",
}

NAIVE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?$")


def _table_columns(conn):
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]
    return {
        t: [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')]
        for t in tables
    }


def migrate(conn, dry_run=False):
    """Return (table, column, affected_rows) tuples for changed columns."""
    changed = []
    for table, columns in _table_columns(conn).items():
        for col in columns:
            if col not in CLOCK_COLUMNS or col in PLATFORM_COLUMNS:
                continue
            like = (
                f"SELECT COUNT(*) FROM \"{table}\" "
                f"WHERE (\"{col}\" LIKE '____-__-__ __:__%' "
                f"OR \"{col}\" LIKE '____-__-__T__:__%') "
                f"AND \"{col}\" NOT LIKE '%Z' "
                f"AND \"{col}\" NOT LIKE '%+%'"
            )
            count = conn.execute(like).fetchone()[0]
            if not count:
                continue
            if dry_run:
                sample = conn.execute(
                    f'SELECT "{col}" FROM "{table}" WHERE "{col}" IS NOT NULL LIMIT 1'
                ).fetchone()
                print(f"[dry-run] {table}.{col}: {count} row(s), sample={sample[0] if sample else ''}")
            else:
                cur = conn.execute(
                    f'UPDATE "{table}" SET "{col}" = '
                    f"datetime(\"{col}\", '+8 hours') "
                    f'WHERE (("{col}" LIKE \'____-__-__ __:__%\' '
                    f"OR \"{col}\" LIKE '____-__-__T__:__%') "
                    f"AND \"{col}\" NOT LIKE '%Z' "
                    f"AND \"{col}\" NOT LIKE '%+%')"
                )
                print(f"[apply] {table}.{col}: {cur.rowcount} row(s)")
            changed.append((table, col, count))
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Only report, do not write")
    parser.add_argument("--backup-dir", help="Directory for timestamped backup (default: DB directory)")
    args = parser.parse_args(argv)

    if not args.dry_run:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = f"{args.db}.bak-{stamp}"
        if args.backup_dir:
            os.makedirs(args.backup_dir, exist_ok=True)
            backup = os.path.join(args.backup_dir, os.path.basename(backup))
        shutil.copy2(args.db, backup)
        print(f"[backup] {args.db} -> {backup}")

    conn = sqlite3.connect(args.db)
    try:
        migrate(conn, dry_run=args.dry_run)
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
