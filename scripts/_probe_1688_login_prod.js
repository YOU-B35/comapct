
const fs = require('fs');
const path = require('path');
module.paths.push(path.join(__dirname, 'node_modules'));
const { Client } = require('ssh2');
const conn = new Client();
function run(cmd){ return new Promise((resolve,reject)=>{ conn.exec(cmd,(e,s)=>{ if(e) return reject(e); let out=''; s.on('data',d=>out+=d); s.stderr.on('data',d=>out+=d); s.on('close',c=>c?reject(new Error(out)):resolve(out)); }); }); }
conn.on('ready', async ()=>{
  try{
    const db = await run(`python3 - <<'PY'
import sqlite3, json
c=sqlite3.connect('/data/crosshub/data/crosshub.db')
c.row_factory=sqlite3.Row
print('== recent 1688_login_open ==')
for r in c.execute("SELECT id,status,error_code,error_message,created_at,started_at,finished_at FROM agent_task WHERE task_type='1688_login_open' ORDER BY created_at DESC LIMIT 6"):
    print(json.dumps(dict(r),ensure_ascii=False))
print('== recent 1688_session_probe ==')
for r in c.execute("SELECT id,status,error_code,error_message,created_at FROM agent_task WHERE task_type='1688_session_probe' ORDER BY created_at DESC LIMIT 3"):
    print(json.dumps(dict(r),ensure_ascii=False))
print('== active agents ==')
for r in c.execute("SELECT id,status,last_heartbeat_at,hostname FROM integration_agent WHERE tenant_id=5 ORDER BY last_heartbeat_at DESC LIMIT 4"):
    print(json.dumps({k:str(r[k]) for k in r.keys()},ensure_ascii=False))
CT
`);
    console.log('DB>>\n'+db.trim());
    const logs = await run(`docker ps --filter name=crosshub --format '{{.Names}} {{.Status}}' 2>/dev/null; echo '---java---'; docker logs crosshub-java --since 2h 2>&1 | grep -aiE '1688|login|Login|A1688|Exception|error' | tail -80`);
    console.log('\nJAVA>>\n'+logs.trim());
  }catch(e){ console.error('ERR',e.message); process.exitCode=1; } finally { conn.end(); }
}).connect({host:'124.223.27.98', port:22, username:'root', privateKey:fs.readFileSync(process.env.USERPROFILE+'\\.ssh\\lhkp-o3wazsuv'), readyTimeout:120000});
