import sqlite3
import tempfile
import unittest

from app.monitor_db import init_monitor_schema, init_monitor_result_schema
from app.monitor_worker_service import analyze_products, persist_snapshot


def _seed_snapshot(conn):
    conn.execute(
        """INSERT INTO monitor_snapshot (id, tenant_id, target_id, platform, snapshot_at, product_count,
           recent_launch_count, sales_outlier_count, report_md_path, report_xlsx_path, created_at)
           VALUES ('ms_prev', 1, 'mt_1', '1688', '2026-08-20 08:00:00', 1, 0, 0, '', '', '2026-08-20 08:00:00')"""
    )
    conn.execute(
        """INSERT INTO monitor_product_snapshot (
           id, tenant_id, snapshot_id, target_id, product_id, product_name, category, price,
           daily_sales, total_sales, listed_at, url, shop_name, shop_url, rank, price_range,
           sale_text, dropship_7d, dropship_30d, dropship_heat, rebuy_rate, shop_return_rate,
           quality_rate, shop_fans, attrs_json, is_pinned, status, expired, suspicious, raw_json, created_at)
           VALUES ('mps_prev', 1, 'ms_prev', 'mt_1', '930671411701', 'KRANK', '', 0.5,
           0, 50000, '2024-08-15', 'https://detail.1688.com/offer/930671411701.html',
           '东博瑞', '', 1, '', '已售5万+件', '', '', 0, '', '', '', 0, '', 1, 'published', 0, 0, '{}', '2026-08-20 08:00:00')"""
    )
    conn.commit()


class Alibaba1688MonitorAnalysisTest(unittest.TestCase):
    def test_daily_sales_delta_and_price_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            init_monitor_schema(conn)
            init_monitor_result_schema(conn)
            _seed_snapshot(conn)

            products = [
                {
                    "product_id": "930671411701",
                    "product_name": "KRANK",
                    "price": 0.6,
                    "total_sales": 51200,
                    "daily_sales": 0,
                    "listed_at": "2024-08-15",
                    "url": "https://detail.1688.com/offer/930671411701.html",
                    "rank": 1,
                    "status": "published",
                    "expired": 0,
                }
            ]
            analysis = analyze_products(conn, 1, "mt_1", "2026-08-20 10:00:00", products)
            self.assertEqual(products[0]["daily_sales"], 1200)  # 51200 - 50000
            self.assertNotIn("suspicious", products[0])
            types = {s[0] for s in analysis["signals"]}
            self.assertIn("price_change", types)

            persist_snapshot(
                conn,
                snapshot_id="ms_cur",
                tenant_id=1,
                target_id="mt_1",
                platform="1688",
                snapshot_at="2026-08-20 10:00:00",
                products=products,
                analysis=analysis,
                report_paths={"report_md_rel": "m.md", "report_xlsx_rel": "m.xlsx"},
            )
            row = conn.execute(
                "SELECT daily_sales, total_sales, shop_name, rank, status, suspicious FROM monitor_product_snapshot WHERE snapshot_id='ms_cur'"
            ).fetchone()
            self.assertEqual(row["daily_sales"], 1200)
            self.assertEqual(row["status"], "published")

    def test_suspicious_negative_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            init_monitor_schema(conn)
            init_monitor_result_schema(conn)
            _seed_snapshot(conn)
            products = [
                {
                    "product_id": "930671411701",
                    "product_name": "KRANK",
                    "price": 0.5,
                    "total_sales": 100,
                    "daily_sales": 0,
                    "listed_at": "2024-08-15",
                    "url": "",
                    "rank": 1,
                    "status": "published",
                    "expired": 0,
                }
            ]
            analyze_products(conn, 1, "mt_1", "2026-08-20 10:00:00", products)
            self.assertEqual(products[0]["suspicious"], 1)
            self.assertEqual(products[0]["daily_sales"], 0)
