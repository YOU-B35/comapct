import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from migrate_db_utc_to_shanghai import migrate


class MigrateTest(unittest.TestCase):
    def _db(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE agent_task (
              id TEXT PRIMARY KEY,
              created_at TEXT,
              started_at TEXT,
              finished_at TEXT
            );
            CREATE TABLE douyin_order (
              id TEXT PRIMARY KEY,
              ordered_at TEXT,
              created_at TEXT
            );
            CREATE TABLE mix (
              id TEXT PRIMARY KEY,
              updated_at TEXT,
              expires_at TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO agent_task VALUES ('a', '2026-08-22 01:01:15', '2026-08-22 01:04:51', '2026-08-22 01:06:03')"
        )
        conn.execute("INSERT INTO douyin_order VALUES ('o', '2026-08-13 23:49:21', '2026-08-14 17:33:31')")
        conn.execute("INSERT INTO mix VALUES ('m', '2026-08-22 01:00:00', '2026-08-22T01:00:00Z')")
        conn.commit()
        conn.close()
        return path

    def test_clock_columns_shift_plus_8(self):
        path = self._db()
        conn = sqlite3.connect(path)
        migrate(conn, dry_run=False)
        conn.commit()
        row = conn.execute("SELECT created_at, started_at, finished_at FROM agent_task WHERE id='a'").fetchone()
        self.assertEqual(row, ("2026-08-22 09:01:15", "2026-08-22 09:04:51", "2026-08-22 09:06:03"))
        conn.close()
        os.remove(path)

    def test_platform_and_iso_columns_untouched(self):
        path = self._db()
        conn = sqlite3.connect(path)
        migrate(conn, dry_run=False)
        conn.commit()
        row = conn.execute("SELECT ordered_at, created_at FROM douyin_order WHERE id='o'").fetchone()
        # ordered_at is platform time (never migrated); created_at is server clock (migrated +8).
        self.assertEqual(row, ("2026-08-13 23:49:21", "2026-08-15 01:33:31"))
        row = conn.execute("SELECT updated_at, expires_at FROM mix WHERE id='m'").fetchone()
        self.assertEqual(row, ("2026-08-22 09:00:00", "2026-08-22T01:00:00Z"))
        conn.close()
        os.remove(path)

    def test_dry_run_does_not_write(self):
        path = self._db()
        conn = sqlite3.connect(path)
        migrate(conn, dry_run=True)
        row = conn.execute("SELECT created_at FROM agent_task WHERE id='a'").fetchone()
        self.assertEqual(row, ("2026-08-22 01:01:15",))
        conn.close()
        os.remove(path)


if __name__ == "__main__":
    unittest.main()
