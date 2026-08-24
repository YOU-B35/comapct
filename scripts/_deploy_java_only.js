const fs = require('fs');
const path = require('path');
const glob = require('glob');
const ssh = require('./lib/deploy-ssh');

const ROOT = path.resolve(__dirname, '..');
const JAR_DIR = process.env.JAR_DIR || path.join(ROOT, 'backend/java/target');
const DOCKERFILE = path.join(ROOT, 'deploy/Dockerfile.java');
const REMOTE_ROOT = '/data/crosshub';

async function findJar() {
  const pattern = path.join(JAR_DIR, 'temu-api-*.jar');
  return new Promise((resolve, reject) => {
    glob(pattern, { strict: false }, (err, files) => {
      if (err) return reject(err);
      if (!files || files.length === 0) {
        reject(new Error(`No JAR found matching ${pattern}. Set JAR_DIR env var to override.`));
      } else {
        files.sort();
        resolve(files[files.length - 1]); // Take latest
      }
    });
  });
}

async function main() {
  let conn;
  try {
    // Locate JAR dynamically
    const JAR = await findJar();
    console.log(`[JAR] Using: ${JAR}`);

    if (!fs.existsSync(DOCKERFILE)) {
      throw new Error(`Dockerfile not found: ${DOCKERFILE}`);
    }

    conn = await ssh.connect();

    // Create remote directory
    await ssh.exec(conn, `mkdir -p ${REMOTE_ROOT}`);

    // Upload JAR and Dockerfile
    console.log(`[UPLOAD] ${JAR} (${Math.round(fs.statSync(JAR).size / 1048576)}MB)`);
    await ssh.put(conn, JAR, `${REMOTE_ROOT}/app.jar`);
    console.log(`[UPLOAD] ${DOCKERFILE}`);
    await ssh.put(conn, DOCKERFILE, `${REMOTE_ROOT}/Dockerfile.java`);

    // Rebuild and verify
    console.log('==> rebuild crosshub-java (docker build + force-recreate java only)');
    const out = await ssh.exec(conn, [
      'set -e', 'cd /data/crosshub',
      'docker build -f Dockerfile.java -t crosshub-java:latest .',
      'docker compose -f docker-compose.yml up -d --force-recreate crosshub-java',
      'sleep 8',
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
