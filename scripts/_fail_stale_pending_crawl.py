import sqlite3

c = sqlite3.connect(r"D:\NIUBI\SaaS-HZ_WEB_Demo\backend\data\crosshub.db")
# mark stale pending crawl as failed so new refresh can proceed cleanly
c.execute(
    """
    UPDATE temu_crawl_job
    SET status='failed',
        error_code='CRAWL_INTERRUPTED',
        error_message='overnight pending stale; interrupted for retest',
        finished_at=datetime('now','localtime')
    WHERE id='9d61030c-9b56-419b-afdb-b3b7493824f1' AND status='pending'
    """
)
print("updated=", c.total_changes)
c.commit()
print(c.execute("SELECT id,status,error_code FROM temu_crawl_job WHERE id='9d61030c-9b56-419b-afdb-b3b7493824f1'").fetchone())
print("report_time=", c.execute("SELECT MAX(report_time) FROM temu_sale WHERE tenant_id=5").fetchone()[0])
