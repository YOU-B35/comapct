/* Temp: check production java container health and logs. */
const fs = require('fs');
const path = require('path');
module.paths.push(path.join(__dirname, 'node_modules'));
const { Client } = require('ssh2');
const conn = new Client();
function run(cmd) { return new Promise((resolve, reject) => { conn.exec(cmd, (e, s) => { if (e) return reject(e); let out=''; s.on('data', d => out += d); s.stderr.on('data', d => out += d); s.on('close', c => c ? reject(new Error(out)) : resolve(out)); }); }); }
conn.on('ready', async () => {
  try {
    const ps = await run("docker ps --filter name=crosshub --format '{{.Names}} {{.Status}}'");
    console.log('PS:\n' + ps.trim());
    const logs = await run("docker logs crosshub-java --tail 220 2>&1 | grep -A 30 -B 5 -E 'Exception|Error|Caused by|SQL' | tail -80");
    console.log('LOGS:\n' + logs.trim());
  } catch (e) { console.error('ERR', e.message); process.exitCode = 1; } finally { conn.end(); }
}).connect({ host: '124.223.27.98', port: 22, username: 'root', privateKey: fs.readFileSync(process.env.USERPROFILE + '\\.ssh\\lhkp-o3wazsuv'), readyTimeout: 120000 });
