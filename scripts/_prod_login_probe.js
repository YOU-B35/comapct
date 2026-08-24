/* Temp: production recent login task + agent state. */
const fs = require('fs');
const path = require('path');
module.paths.push(path.join(__dirname, 'node_modules'));
const { Client } = require('ssh2');
const conn = new Client();
function run(cmd) { return new Promise((resolve, reject) => { conn.exec(cmd, (e, s) => { if (e) return reject(e); let out=''; s.on('data', d => out += d); s.stderr.on('data', d => out += d); s.on('close', c => c ? reject(new Error(out)) : resolve(out)); }); }); }
conn.on('ready', async () => {
  try {
    const out = await run(
      "python3 - <<'PY'\n" +
      "import sqlite3\n" +
      "c=sqlite3.connect('/data/crosshub/data/crosshub.db')\n" +
      "c.row_factory=sqlite3.Row\n" +
      "for r in c.execute(\"SELECT id, agent_id, status, error_code, error_message, created_at, started_at, finished_at FROM agent_task WHERE task_type='1688_login_open' ORDER BY created_at DESC LIMIT 4\"):\n" +
      "  print('TASK', dict(r))\n" +
      "for r in c.execute(\"SELECT id, status, last_heartbeat_at FROM integration_agent WHERE tenant_id=5 AND status='active' ORDER BY last_heartbeat_at DESC LIMIT 3\"):\n" +
      "  print('AGENT', dict(r))\n" +
      "PY"
    );
    console.log(out.trim());
  } catch (e) { console.error('ERR', e.message); process.exitCode = 1; } finally { conn.end(); }
}).connect({ host: '124.223.27.98', port: 22, username: 'root', privateKey: fs.readFileSync(process.env.USERPROFILE + '\\.ssh\\lhkp-o3wazsuv'), readyTimeout: 120000 });
