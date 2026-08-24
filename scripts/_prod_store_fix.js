/* Temp: move default-profile data to the verified default account (泰州安可 13996db6). */
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
      "o=c.execute(\"UPDATE alibaba1688_order SET store_id='13996db6-30bc-4d24-920f-47c78bdc6468' WHERE store_id='default' AND tenant_id=5 AND order_no NOT IN (SELECT order_no FROM alibaba1688_order WHERE tenant_id=5 AND store_id='13996db6-30bc-4d24-920f-47c78bdc6468')\")\n" +
      "i=c.execute(\"UPDATE alibaba1688_order_item SET store_id='13996db6-30bc-4d24-920f-47c78bdc6468' WHERE store_id='default' AND tenant_id=5 AND (order_no, line_id) NOT IN (SELECT order_no, line_id FROM alibaba1688_order_item WHERE tenant_id=5 AND store_id='13996db6-30bc-4d24-920f-47c78bdc6468')\")\n" +
      "p=c.execute(\"UPDATE alibaba1688_product SET store_id='13996db6-30bc-4d24-920f-47c78bdc6468' WHERE store_id='9b5d3de4-1ca9-446a-b9b4-47bad1226b91' AND tenant_id=5\")\n" +
      "c.commit()\n" +
      "print('MOVED', o.rowcount, i.rowcount, p.rowcount)\n" +
      "dup=c.execute(\"SELECT COUNT(*) FROM alibaba1688_order WHERE store_id='default' AND tenant_id=5 AND order_no IN (SELECT order_no FROM alibaba1688_order WHERE tenant_id=5 AND store_id='13996db6-30bc-4d24-920f-47c78bdc6468')\").fetchone()[0]\n" +
      "d1=c.execute(\"DELETE FROM alibaba1688_order_item WHERE store_id='default' AND tenant_id=5 AND (order_no, line_id) IN (SELECT order_no, line_id FROM alibaba1688_order_item WHERE tenant_id=5 AND store_id='13996db6-30bc-4d24-920f-47c78bdc6468')\")\n" +
      "d2=c.execute(\"DELETE FROM alibaba1688_order WHERE store_id='default' AND tenant_id=5 AND order_no IN (SELECT order_no FROM alibaba1688_order WHERE tenant_id=5 AND store_id='13996db6-30bc-4d24-920f-47c78bdc6468')\")\n" +
      "c.commit()\n" +
      "print('DUP', dup, 'DELETED', d1.rowcount, d2.rowcount)\n" +
      "for t in ('alibaba1688_order','alibaba1688_product'):\n" +
      "  print('STORE_KEYS', t, c.execute('SELECT store_id, COUNT(*) FROM '+t+' GROUP BY store_id').fetchall())\n" +
      "PY"
    );
    console.log(out.trim());
  } catch (e) { console.error('ERR', e.message); process.exitCode = 1; } finally { conn.end(); }
}).connect({ host: '124.223.27.98', port: 22, username: 'root', privateKey: fs.readFileSync(process.env.USERPROFILE + '\\.ssh\\lhkp-o3wazsuv'), readyTimeout: 120000 });
