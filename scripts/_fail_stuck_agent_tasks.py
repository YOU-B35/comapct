"""Fail stuck agent_task rows that block Amazon sync queue."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "backend/data/crosshub.db"
MSG = "Agent 重启后手动解除卡住的 running 任务"


def main() -> None:
    conn = sqlite3.connect(DB)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.cursor()
    running = cur.execute(
        """
        SELECT id, started_at FROM agent_task
        WHERE status='running' AND task_type='amazon_sync'
        """
    ).fetchall()
    for task_id, started in running:
        cur.execute(
            """
            UPDATE agent_task
            SET status='failed', error_code='CRAWL_INTERRUPTED', error_message=?, finished_at=?
            WHERE id=?
            """,
            (MSG, now, task_id),
        )
        cur.execute(
            """
            UPDATE amazon_sync_job
            SET status='failed', error_message=?, finished_at=?
            WHERE agent_task_id=? AND status IN ('pending','running')
            """,
            (MSG, now, task_id),
        )
        print("failed running:", task_id, started)

    pending = cur.execute(
        """
        SELECT id FROM agent_task
        WHERE status='pending' AND task_type='amazon_sync'
        """
    ).fetchall()
    for (task_id,) in pending:
        cur.execute(
            """
            UPDATE agent_task
            SET status='failed', error_code='CRAWL_INTERRUPTED', error_message=?, finished_at=?
            WHERE id=?
            """,
            (MSG, now, task_id),
        )
        print("failed pending:", task_id)
    conn.commit()


if __name__ == "__main__":
    main()
