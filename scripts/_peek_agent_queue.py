import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parents[1] / "backend/data/crosshub.db"
c = sqlite3.connect(db)
c.row_factory = sqlite3.Row
print("=== running agent_task ===")
for row in c.execute(
    "SELECT id, tenant_id, agent_id, task_type, status, started_at, error_message "
    "FROM agent_task WHERE status IN ('running','pending') AND task_type='amazon_sync'"
):
    print(dict(row))
print("=== integration_agent (recent heartbeat) ===")
for row in c.execute(
    "SELECT id, tenant_id, name, status, last_heartbeat_at FROM integration_agent "
    "ORDER BY last_heartbeat_at DESC LIMIT 6"
):
    print(dict(row))
 