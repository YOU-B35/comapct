// Temp: upload new CrossHub-Sync-Helper.zip to prod downloads using SSH private key.
const fs = require('fs');
const path = require('path');
module.paths.push(path.join(__dirname, 'node_modules'));
const { Client } = require('ssh2');
const conn = new Client();
const LOCAL_ZIP = path.resolve(__dirname, '..', 'dist', 'CrossHub-Sync-Helper.zip');
const REMOTE_DIR = '/opt/1panel/www/sites/www.yoto.work/index/crosshub/downloads';
const REMOTE_ZIP = `${REMOTE_DIR}/CrossHub-Sync-Helper.zip`;
function run(cmd){ return new Promise((resolve,reject)=>{ conn.exec(cmd,(e,s)=>{ if(e) return reject(e); let out=''; s.on('data',d=>out+=d); s.stderr.on('data',d=>out+=d); s.on('close',c=>c?reject(new Error(out)):resolve(out)); }); }); }
function put(sftp, local, remote){ return new Promise((resolve,reject)=>{ sftp.fastPut(local, remote, { mode: 0o644 }, (e)=> e?reject(e):resolve() ); }); }
conn.on('ready', async ()=>{
  try{
    const sizeMb = (fs.statSync(LOCAL_ZIP).size/1048576).toFixed(1);
    console.log(`==> upload ${LOCAL_ZIP} (${sizeMb} MB)`);
    await run(`mkdir -p ${REMOTE_DIR}`);
    const sftp = await new Promise((resolve,reject)=> conn.sftp((e,s)=> e?reject(e):resolve(s)));
    await put(sftp, LOCAL_ZIP, REMOTE_ZIP);
    const out = await run(`ls -lh ${REMOTE_ZIP}; sha256sum ${REMOTE_ZIP}`);
    console.log(out.trim());
    const localSha = require('crypto').createHash('sha256').update(fs.readFileSync(LOCAL_ZIP)).digest('hex');
    console.log('local_sha256=' + localSha);
    console.log('==> uploaded');
  }catch(e){ console.error('ERR', e.message); process.exitCode=1; } finally { conn.end(); }
}).connect({host:'124.223.27.98', port:22, username:'root', privateKey:fs.readFileSync(process.env.USERPROFILE+'\\.ssh\\lhkp-o3wazsuv'), readyTimeout:120000});
