/**
 * Inspect Douyin login tasks + force-reclaim busy ones for a tenant.
 * CROSSHUB_SSH_PASSWORD=... node scripts/_diag_douyin_login_tasks.js [tenantId]
 */
const path = require('path')
module.paths.push(path.join(__dirname, 'node_modules'))
const { Client } = require('ssh2')

const tenantId = Number(process.argv[2] || 5)
const password = process.env.CROSSHUB_SSH_PASSWORD
if (!password) {
  console.error('CROSSHUB_SSH_PASSWORD required')
  process.exit(1)
}

const sql = `
python3 - <<PY
import sqlite3
from datetime import datetime
db="/data/crosshub/data/crosshub.db"
tid=${tenantId}
conn=sqlite3.connect(db)
conn.row_factory=sqlite3.Row
cur=conn.cursor()
print("=== recent agents ===")
for r in cur.execute("""
  SELECT id, name, status, last_heartbeat_at, bound_user_id, substr(coalesce(machine_fingerprint,''),1,12) AS fp
  FROM integration_agent
  WHERE tenant_id=?
  ORDER BY datetime(last_heartbeat_at) DESC
  LIMIT 8
""", (tid,)):
  print(dict(r))
print("=== busy douyin tasks ===")
for r in cur.execute("""
  SELECT id, task_type, status, agent_id, created_at, started_at, finished_at,
         substr(coalesce(error_message,''),1,160) AS err
  FROM agent_task
  WHERE tenant_id=?
    AND status IN ('pending','running')
    AND task_type LIKE 'douyin%'
  ORDER BY datetime(created_at) DESC LIMIT 20
""", (tid,)):
  print(dict(r))
print("=== recent douyin_login_open ===")
for r in cur.execute("""
  SELECT id, task_type, status, agent_id, created_at, started_at, finished_at,
         substr(coalesce(error_message,''),1,200) AS err
  FROM agent_task
  WHERE tenant_id=? AND task_type='douyin_login_open'
  ORDER BY datetime(created_at) DESC LIMIT 12
""", (tid,)):
  print(dict(r))
print("=== session snapshot ===")
try:
  for r in cur.execute("SELECT payload_json FROM douyin_session_snapshot WHERE tenant_id=? LIMIT 1", (tid,)):
    print((r["payload_json"] or "")[:700])
except Exception as e:
  print("snapshot_err", e)
now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
n=cur.execute("""
  UPDATE agent_task
  SET status='failed',
      error_code='DY_SYNC_FAILED',
      error_message='运维强制清理：请重启 Helper 后重新打开登录',
      finished_at=?
  WHERE tenant_id=?
    AND status IN ('pending','running')
    AND task_type IN ('douyin_login_open','douyin_session_probe','douyin_sync','douyin_products_sync')
""", (now, tid)).rowcount
conn.commit()
print("force_cleared=", n)
conn.close()
PY
`.trim()

const conn = new Client()
conn
  .on('ready', () => {
    conn.exec(sql, (err, stream) => {
      if (err) {
        console.error(err)
        process.exit(1)
      }
      stream.on('data', (d) => process.stdout.write(d))
      stream.stderr.on('data', (d) => process.stderr.write(d))
      stream.on('close', (code) => {
        conn.end()
        process.exit(code || 0)
      })
    })
  })
  .on('error', (e) => {
    console.error(e.message || e)
    process.exit(1)
  })
  .connect({
    host: process.env.CROSSHUB_SSH_HOST || '124.223.27.98',
    username: process.env.CROSSHUB_SSH_USER || 'root',
    password,
    readyTimeout: 60000,
  })
