import sqlite3
import unittest

from app.monitor_db import init_monitor_schema
from app.monitor_schedule_enqueuer import enqueue_due_jobs


def _seed(conn):
    conn.execute(
        """INSERT INTO monitor_target (id, tenant_id, platform, target_type, label, target_url, host,
           status, crawl_strategy, freshness_minutes, latest_snapshot_id, latest_snapshot_at, created_at, updated_at)
           VALUES ('mt_1', 1, '1688', 'shop', '东博瑞', 'https://shop16yx1905b2433.1688.com',
           'shop16yx1905b2433.1688.com', 'active', '1688_shop_topn', 120, NULL, NULL, '2026-08-20 00:00:00', '2026-08-20 00:00:00')"""
    )
    conn.execute(
        """INSERT INTO monitor_schedule (id, tenant_id, target_id, enabled, schedule_type, cron_expr,
           interval_minutes, next_run_at, last_run_at, max_products, retry_limit, created_at, updated_at)
           VALUES ('msch_1', 1, 'mt_1', 1, 'interval', '', 120, '2026-08-20 09:00:00', NULL, 20, 1,
           '2026-08-20 00:00:00', '2026-08-20 00:00:00')"""
    )
    conn.commit()


class MonitorScheduleEnqueuerTest(unittest.TestCase):
    def test_enqueues_due_job_and_advances_next_run(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_monitor_schema(conn)
        _seed(conn)
        job_ids = enqueue_due_jobs(conn, now="2026-08-20 10:00:00", jitter_seconds=0)
        self.assertEqual(len(job_ids), 1)
        job = conn.execute("SELECT * FROM monitor_job WHERE id = ?", (job_ids[0],)).fetchone()
        self.assertEqual(job["trigger_type"], "scheduled")
        self.assertEqual(job["platform"], "1688")
        sched = conn.execute("SELECT * FROM monitor_schedule WHERE id = 'msch_1'").fetchone()
        self.assertEqual(sched["next_run_at"], "2026-08-20 12:00:00")

    def test_skips_target_with_running_job(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_monitor_schema(conn)
        _seed(conn)
        conn.execute(
            """INSERT INTO monitor_job (id, tenant_id, target_id, schedule_id, platform, trigger_type,
               force, status, attempt_no, queued_at, started_at, finished_at, worker_id, error_code,
               error_message, error_detail, snapshot_id, created_by, reason)
               VALUES ('mj_busy', 1, 'mt_1', 'msch_1', '1688', 'manual', 0, 'running', 1,
               '2026-08-20 09:00:00', '2026-08-20 09:00:01', NULL, '', NULL, NULL, NULL, NULL, NULL, '')"""
        )
        conn.commit()
        job_ids = enqueue_due_jobs(conn, now="2026-08-20 10:00:00", jitter_seconds=0)
        self.assertEqual(job_ids, [])
