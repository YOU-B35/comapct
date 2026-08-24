/* Temp: verify production 1688 store keys and bound stores. */
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
      "print('ORDER_STORE_KEYS')\n" +
      "for r in c.execute('SELECT store_id, COUNT(*) FROM alibaba1688_order GROUP BY store_id'): print(r)\n" +
      "print('PRODUCT_STORE_KEYS')\n" +
      "for r in c.execute('SELECT store_id, COUNT(*) FROM alibaba1688_product GROUP BY store_id'): print(r)\n" +
      "print('BOUND_1688_STORES')\n" +
      "for r in c.execute(\"SELECT id, store_name, account FROM platform_account WHERE platform='1688'\"): print(r)\n" +
      "print('SESSION_SNAPSHOT_KEYS')\n" +
      "for r in c.execute('SELECT store_id, substr(payload_json,1,120) FROM alibaba1688_session_snapshot'): print(r)\n" +
      "PY"
    );
    console.log(out.trim());
  } catch (e) { console.error('ERR', e.message); process.exitCode = 1; } finally { conn.end(); }
}).connect({ host: '124.223.27.98', port: 22, username: 'root', privateKey: fs.readFileSync(process.env.USERPROFILE + '\\.ssh\\lhkp-o3wazsuv'), readyTimeout: 120000 });
