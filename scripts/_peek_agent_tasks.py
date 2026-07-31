import sqlite3
c = sqlite3.connect(r"D:\NIUBI\SaaS-HZ_WEB_Demo\backend\data\crosshub.db")
print("recent agent_task:")
for r in c.execute(
    """
    SELECT id, task_type, status, created_at, started_at, finished_at, error_code,
           substr(COALESCE(error_message,''),1,120)
    FROM agent_task WHERE tenant_id=5
    ORDER BY created_at DESC LIMIT 8
    """
):
    print(r)
