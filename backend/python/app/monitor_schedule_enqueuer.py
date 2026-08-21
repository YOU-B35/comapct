"""Enqueue due monitor jobs from monitor_schedule."""
from __future__ import annotations

import random
import sqlite3
import uuid
from datetime import datetime, timedelta


def enqueue_due_jobs(
    conn: sqlite3.Connection,
    *,
    now: str | None = None,
    jitter_seconds: int = 600,
) -> list[str]:
    if now is None:
        from app.monitor_worker_service import now_text

        now = now_text()
    rows = conn.execute(
        """
        SELECT s.id AS schedule_id, s.tenant_id, s.target_id, s.interval_minutes, t.platform
        FROM monitor_schedule s
        JOIN monitor_target t ON t.id = s.target_id AND t.tenant_id = s.tenant_id
        WHERE s.enabled = 1 AND t.status = 'active'
          AND (s.next_run_at IS NULL OR s.next_run_at <= ?)
        """,
        (now,),
    ).fetchall()
    enqueued: list[str] = []
    for row in rows:
        target_id = row["target_id"]
        busy = conn.execute(
            """
            SELECT 1 FROM monitor_job
            WHERE tenant_id = ? AND target_id = ? AND status IN ('pending', 'running')
            LIMIT 1
            """,
            (row["tenant_id"], target_id),
        ).fetchone()
        if busy:
            continue
        job_id = f"mj_{uuid.uuid4().hex}"
        conn.execute(
            """
            INSERT INTO monitor_job (
              id, tenant_id, target_id, schedule_id, platform, trigger_type, force, status,
              attempt_no, queued_at, started_at, finished_at, worker_id, error_code, error_message,
              error_detail, snapshot_id, created_by, reason
            ) VALUES (?, ?, ?, ?, ?, 'scheduled', 0, 'pending', 1, ?, NULL, NULL, '', NULL, NULL, NULL, NULL, NULL, 'scheduled')
            """,
            (job_id, row["tenant_id"], target_id, row["schedule_id"], row["platform"], now),
        )
        interval_minutes = max(1, int(row["interval_minutes"] or 1440))
        next_run = _next_run_at(now, interval_minutes, jitter_seconds)
        conn.execute(
            "UPDATE monitor_schedule SET next_run_at = ?, last_run_at = ?, updated_at = ? WHERE id = ?",
            (next_run, now, now, row["schedule_id"]),
        )
        enqueued.append(job_id)
    conn.commit()
    return enqueued


def _next_run_at(now: str, interval_minutes: int, jitter_seconds: int) -> str:
    base = datetime.strptime(now[:19], "%Y-%m-%d %H:%M:%S")
    jitter = random.randint(0, max(0, jitter_seconds))
    return (base + timedelta(minutes=interval_minutes, seconds=jitter)).strftime("%Y-%m-%d %H:%M:%S")
