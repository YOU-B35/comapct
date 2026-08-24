const { Client } = require('ssh2');
const fs = require('fs');

const HOST = '124.223.27.98';
const KEY = 'C:/Users/Administrator/.ssh/lhkp-o3wazsuv';

const cmd = `
echo "=== kuaishou.log today errors/fail (full) ==="
grep -E "2026-08-21" /opt/autoMedia-social-auto-upload/deploy/data/logs/kuaishou.log | grep -iE "error|fail|失败|timeout|超时|发布|重试|cookie" | tail -80
echo
echo "=== kuaishou.log tail 60 ==="
tail -60 /opt/autoMedia-social-auto-upload/deploy/data/logs/kuaishou.log
echo
echo "=== account file D58383b2 ==="
ls -la /opt/autoMedia-social-auto-upload/deploy/data/cookiesFile/ | grep -i "D58383b2" 
python3 - <<'PY'
import sqlite3, json
con=sqlite3.connect('/opt/autoMedia-social-auto-upload/deploy/data/db/database.db')
con.row_factory=sqlite3.Row
for row in con.execute("SELECT id,type,filePath,userName,status,owner_id,bound_agent_hostname FROM user_info WHERE filePath LIKE '%D58383b2%'").fetchall():
    print(json.dumps({k:row[k] for k in row.keys()}, ensure_ascii=False))
PY
echo
echo "=== automedia docker logs last 3h publish/worker ==="
docker logs automedia-social-auto-upload --since 3h 2>&1 | grep -aE "publish|worker|server_fallback|postVideoBatch|checkAccount" | grep -avE "login-agent/(heartbeat|poll)" | tail -60
`;

const c = new Client();
c.on('ready', () => {
  c.exec(cmd, (err, stream) => {
    if (err) { console.error(err); process.exit(1); }
    let out = '';
    stream.on('data', (d) => (out += d.toString()));
    stream.stderr.on('data', (d) => (out += d.toString()));
    stream.on('close', () => { console.log(out); c.end(); });
  });
});
c.on('error', (e) => { console.error('SSH_ERR', e.message); process.exit(1); });
c.connect({ host: HOST, port: 22, username: 'root', privateKey: fs.readFileSync(KEY), readyTimeout: 30000 });
