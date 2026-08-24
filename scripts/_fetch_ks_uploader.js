const fs = require('fs');
const path = require('path');
const ssh = require('./lib/deploy-ssh');

const REMOTE = '/opt/autoMedia-social-auto-upload/app/uploader/ks_uploader/main.py';
const OUT = path.join(process.env.TEMP || path.join(process.env.USERPROFILE || '/tmp', 'AppData/Local/Temp'), 'ks-fix');

async function main() {
  try {
    fs.mkdirSync(OUT, { recursive: true });
    const LOCAL = path.join(OUT, 'ks_main.py');

    const conn = await ssh.connect();
    console.log(`[DOWNLOAD] ${REMOTE} -> ${LOCAL}`);
    await ssh.get(conn, REMOTE, LOCAL);
    console.log('[OK] Download completed');
    conn.end();
  } catch (err) {
    console.error(`[ERROR] ${err.message}`);
    process.exit(1);
  }
}

main();
