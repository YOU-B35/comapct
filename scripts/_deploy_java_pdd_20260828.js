// One-off deploy: PDD fixes (c975163) — mirrors _deploy_java_only.js without the glob dependency.
const fs = require('fs');
const path = require('path');
module.paths.push(path.join(__dirname, 'node_modules'));
const ssh = require('./lib/deploy-ssh');

const ROOT = path.resolve(__dirname, '..');
const JAR = path.join(ROOT, 'backend', 'java', 'target', 'temu-api-0.1.0.jar');
const DOCKERFILE = path.join(ROOT, 'deploy', 'Dockerfile.java');
const REMOTE_ROOT = '/data/crosshub';

async function main() {
  let conn;
  try {
    if (!fs.existsSync(JAR)) throw new Error(`JAR not found: ${JAR}`);
    if (!fs.existsSync(DOCKERFILE)) throw new Error(`Dockerfile not found: ${DOCKERFILE}`);
    console.log(`[JAR] Using: ${JAR} (${Math.round(fs.statSync(JAR).size / 1048576)}MB)`);

    conn = await ssh.connect();
    await ssh.exec(conn, `mkdir -p ${REMOTE_ROOT}`);

    console.log(`[UPLOAD] app.jar`);
    await ssh.put(conn, JAR, `${REMOTE_ROOT}/app.jar`);
    console.log(`[UPLOAD] Dockerfile.java`);
    await ssh.put(conn, DOCKERFILE, `${REMOTE_ROOT}/Dockerfile.java`);

    console.log('==> rebuild crosshub-java (docker build + force-recreate java only)');
    const out = await ssh.exec(conn, [
      'set -e', 'cd /data/crosshub',
      'docker build -f Dockerfile.java -t crosshub-java:latest .',
      'docker compose -f docker-compose.yml up -d --force-recreate crosshub-java',
      'sleep 10',
      'docker ps --filter name=crosshub-java --format "table {{.Names}}\\t{{.Status}}"',
      'curl -s http://127.0.0.1:18080/api/helper/update-info || true',
      'curl -s -o /dev/null -w "\\njava_health=%{http_code}\\n" http://127.0.0.1:18080/api/temu/shops || true',
    ].join('\n'));
    console.log(out.trim());
    console.log('[OK] Java deploy completed successfully');
  } catch (err) {
    console.error(`[ERROR] ${err.message}`);
    process.exit(1);
  } finally {
    if (conn) conn.end();
  }
}

main();
