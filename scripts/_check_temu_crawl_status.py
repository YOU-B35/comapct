import sqlite3

c = sqlite3.connect(r"D:\NIUBI\SaaS-HZ_WEB_Demo\backend\data\crosshub.db")
print("report_time=", c.execute("SELECT MAX(report_time) FROM temu_sale WHERE tenant_id=5").fetchone()[0])
print("sale_count=", c.execute("SELECT COUNT(*) FROM temu_sale WHERE tenant_id=5").fetchone()[0])
print("jobs:")
for r in c.execute(
    """
    SELECT id, status, created_at, finished_at, error_code,
           substr(COALESCE(error_message, ''), 1, 200)
    FROM temu_crawl_job
    WHERE tenant_id=5
    ORDER BY created_at DESC
    LIMIT 8
    """
):
    print(r)
