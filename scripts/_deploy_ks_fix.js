const fs = require('fs');
const path = require('path');
const ssh = require('./lib/deploy-ssh');

const SRC = path.join(process.env.TEMP || path.join(process.env.USERPROFILE || '/tmp', 'AppData/Local/Temp'), 'ks-fix');

async function main() {
  let conn;
  try {
    conn = await ssh.connect();

    const stamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
    const remote = '/opt/autoMedia-social-auto-upload/app/uploader/ks_uploader/main.py';

    console.log('== backup + upload ==');
    const bakCmd = [
      'set -e',
      `cp -a ${remote} ${remote}.bak.${stamp}`,
      'echo BACKUP_OK',
    ].join('\n');
    console.log(await ssh.exec(conn, bakCmd));

    await ssh.put(conn, path.join(SRC, 'ks_main.py'), remote);
    console.log(`[OK] uploaded ${remote}`);

    console.log('== docker compose build app ==');
    const buildCmd = [
      'set -e',
      'cd /opt/autoMedia-social-auto-upload/app/deploy/automedia',
      'DOCKER_BUILDKIT=1 docker compose build app 2>&1 | tail -5',
      'echo BUILD_OK',
    ].join('\n');
    console.log(await ssh.exec(conn, buildCmd));

    console.log('== recreate container + verify ==');
    const upCmd = [
      'set -e',
      'cd /opt/autoMedia-social-auto-upload/app/deploy/automedia',
      'docker compose up -d --force-recreate --no-build app',
      'sleep 12',
      "docker ps --filter name=automedia-social-auto-upload --format '{{.Names}} {{.Status}}'",
      "curl -sS -m 15 -o /dev/null -w 'index=%{http_code}\\n' http://127.0.0.1:18302/",
      'echo "== verify ks_uploader constants =="',
      "docker exec automedia-social-auto-upload grep -n 'max_retries = max(150' /app/uploader/ks_uploader/main.py | head -2",
      "docker exec automedia-social-auto-upload grep -n 'timeout=15000' /app/uploader/ks_uploader/main.py | head -2",
      'docker exec automedia-social-auto-upload python -m py_compile /app/uploader/ks_uploader/main.py && echo PY_COMPILE_OK',
    ].join('\n');
    console.log(await ssh.exec(conn, upCmd));

    console.log('[OK] Deploy completed successfully');
  } catch (err) {
    console.error(`[ERROR] ${err.message}`);
    process.exit(1);
  } finally {
    if (conn) conn.end();
  }
}

main();
