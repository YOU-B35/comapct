/**
 * 部署 CrossHub 双后端到 124.223.27.98
 * - Java Docker → 127.0.0.1:18080（不占 34206）
 * - Express Docker → 127.0.0.1:18081（不占 3000 公网）
 * - 静态前端 → www.yoto.work/crosshub/
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
module.paths.push(path.join(__dirname, 'node_modules'));

const REMOTE_ROOT = '/data/crosshub';
const WEB_ROOT = '/opt/1panel/www/sites/www.yoto.work/index/crosshub';
const PROXY_CONF = '/opt/1panel/www/sites/www.yoto.work/proxy/crosshub.conf';

function run(cmd, cwd = ROOT) {
  console.log('>', cmd);
  execSync(cmd, { cwd, stdio: 'inherit', shell: true });
}

function walk(dir, files = [], options = {}, baseDir = dir) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    const rel = path.relative(baseDir, p).replace(/\\/g, '/');
    if (options.skip && options.skip(name, rel, p)) continue;
    if (fs.statSync(p).isDirectory()) walk(p, files, options, baseDir);
    else files.push(p);
  }
  return files;
}

function sftpMkdir(sftp, remoteDir) {
  return new Promise((resolve, reject) => {
    sftp.mkdir(remoteDir, { mode: 0o755 }, (err) => {
      if (!err || err.code === 4) return resolve();
      reject(err);
    });
  });
}

async function sftpEnsureDir(sftp, remoteDir) {
  const parts = remoteDir.split('/').filter(Boolean);
  let cur = '';
  for (const part of parts) {
    cur += `/${part}`;
    await sftpMkdir(sftp, cur);
  }
}

function sftpPut(sftp, local, remote) {
  return new Promise((resolve, reject) => {
    sftp.fastPut(local, remote, { mode: 0o644 }, (err) => (err ? reject(err) : resolve()));
  });
}

async function uploadTree(sftp, localDir, remoteDir, options = {}) {
  await sftpEnsureDir(sftp, remoteDir);
  for (const local of walk(localDir, [], options)) {
    const rel = path.relative(localDir, local).replace(/\\/g, '/');
    const remote = `${remoteDir}/${rel}`;
    await sftpEnsureDir(sftp, path.posix.dirname(remote));
    await sftpPut(sftp, local, remote);
  }
}

function shouldSkipPythonDeploy(name, rel) {
  const parts = rel.split('/').filter(Boolean);
  if (
    name === '.temu-browser-profile' ||
    name === '.aliexpress-browser-profile' ||
    name === '.amazon-browser-profile' ||
    name === 'helper_app' ||
    name === 'exports' ||
    name === '.pytest_cache' ||
    name === '__pycache__' ||
    name === 'Cache' ||
    name === 'Code Cache' ||
    name === 'GPUCache'
  ) {
    return true;
  }
  if (parts.includes('__pycache__')) return true;
  if (parts.includes('.temu-browser-profile')) return true;
  if (parts.includes('.aliexpress-browser-profile')) return true;
  if (parts.includes('.amazon-browser-profile')) return true;
  if (parts.includes('helper_app')) return true;
  if (parts.includes('exports')) return true;
  if (parts.includes('reports')) return true;
  if (parts.includes('tests')) return true;
  if (parts.includes('Cache')) return true;
  if (parts.includes('Code Cache')) return true;
  if (parts.includes('GPUCache')) return true;
  if (rel === '.env') return true;
  if (rel.endsWith('.pyc')) return true;
  return false;
}

function exec(conn, cmd) {
  return new Promise((resolve, reject) => {
    conn.exec(cmd, (err, stream) => {
      if (err) return reject(err);
      let out = '';
      stream.on('data', (d) => {
        process.stdout.write(d);
        out += d;
      });
      stream.stderr.on('data', (d) => process.stderr.write(d));
      stream.on('close', (code) => {
        if (code) reject(new Error(`remote exit ${code}`));
        else resolve(out);
      });
    });
  });
}

async function main() {
  run('node scripts/deploy-preflight.js');
  const { Client } = require('ssh2');
  const ssh = {
    host: process.env.CROSSHUB_SSH_HOST || '',
    port: Number(process.env.CROSSHUB_SSH_PORT || 22),
    username: process.env.CROSSHUB_SSH_USER || 'root',
    password: process.env.CROSSHUB_SSH_PASSWORD || '',
    readyTimeout: 120000,
  };

  console.log('==> build Java JAR');
  run('powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-java.ps1');
  run(
    'powershell -NoProfile -Command ". .\\scripts\\env-java.ps1; mvn -f backend/java/pom.xml -q package -DskipTests"',
  );

  const jarSrc = path.join(ROOT, 'backend/java/target/temu-api-0.1.0.jar');
  if (!fs.existsSync(jarSrc)) throw new Error(`missing jar: ${jarSrc}`);
  const buildDir = path.join(ROOT, 'deploy/.build');
  fs.mkdirSync(buildDir, { recursive: true });
  fs.copyFileSync(jarSrc, path.join(buildDir, 'app.jar'));

  console.log('==> build Vue dist');
  run('npm install', path.join(ROOT, 'dev/vue-site'));
  run('npm run build', path.join(ROOT, 'dev/vue-site'));
  const distDir = path.join(ROOT, 'dev/vue-site/dist');
  if (!fs.existsSync(path.join(distDir, 'index.html'))) throw new Error('missing dist');

  const conn = new Client();
  await new Promise((resolve, reject) => {
    conn.on('ready', resolve).on('error', reject).connect(ssh);
  });

  const sftp = await new Promise((resolve, reject) => {
    conn.sftp((err, s) => (err ? reject(err) : resolve(s)));
  });

  console.log('==> upload deploy bundle');
  await sftpEnsureDir(sftp, REMOTE_ROOT);
  await sftpPut(sftp, path.join(buildDir, 'app.jar'), `${REMOTE_ROOT}/app.jar`);
  await sftpPut(sftp, path.join(ROOT, 'deploy/Dockerfile.java'), `${REMOTE_ROOT}/Dockerfile.java`);
  await sftpPut(sftp, path.join(ROOT, 'deploy/Dockerfile.express'), `${REMOTE_ROOT}/Dockerfile.express`);
  await sftpPut(sftp, path.join(ROOT, 'deploy/Dockerfile.python-worker'), `${REMOTE_ROOT}/Dockerfile.python-worker`);
  await sftpPut(sftp, path.join(ROOT, 'deploy/docker-compose.yml'), `${REMOTE_ROOT}/docker-compose.yml`);
  await sftpPut(sftp, path.join(ROOT, 'deploy/crosshub-proxy.conf'), `${REMOTE_ROOT}/crosshub-proxy.conf`);
  await sftpEnsureDir(sftp, `${REMOTE_ROOT}/scripts`);
  await sftpPut(sftp, path.join(ROOT, 'scripts/monitor-api-smoke.js'), `${REMOTE_ROOT}/scripts/monitor-api-smoke.js`);

  const dbLocal = path.join(ROOT, 'backend/data/crosshub.db');
  if (!process.env.CROSSHUB_SKIP_DB_UPLOAD && fs.existsSync(dbLocal)) {
    await sftpEnsureDir(sftp, `${REMOTE_ROOT}/data`);
    await sftpPut(sftp, dbLocal, `${REMOTE_ROOT}/data/crosshub.db`);
    console.log('  uploaded crosshub.db');
  } else if (process.env.CROSSHUB_SKIP_DB_UPLOAD) {
    console.log('  skip crosshub.db upload (CROSSHUB_SKIP_DB_UPLOAD)');
  }

  const expressDir = path.join(ROOT, 'script/api-server');
  await sftpEnsureDir(sftp, `${REMOTE_ROOT}/express-src`);
  for (const name of ['package.json', 'package-lock.json', 'index.js']) {
    const local = path.join(expressDir, name);
    if (fs.existsSync(local)) {
      await sftpPut(sftp, local, `${REMOTE_ROOT}/express-src/${name}`);
    }
  }

  const pythonDir = path.join(ROOT, 'backend/python');
  await uploadTree(sftp, pythonDir, `${REMOTE_ROOT}/python-src`, { skip: shouldSkipPythonDeploy });

  console.log('==> upload static frontend');
  await uploadTree(sftp, distDir, WEB_ROOT);

  const remoteCmd = [
    `set -e`,
    `mkdir -p ${REMOTE_ROOT}/data ${REMOTE_ROOT}/evidence ${REMOTE_ROOT}/reports ${WEB_ROOT}`,
    `cp ${REMOTE_ROOT}/crosshub-proxy.conf ${PROXY_CONF}`,
    `cd ${REMOTE_ROOT}`,
    `docker build -f Dockerfile.java -t crosshub-java:latest .`,
    `docker build -f Dockerfile.express -t crosshub-express:latest express-src`,
    `docker compose -f docker-compose.yml up -d --force-recreate crosshub-java crosshub-express`,
    `docker compose -f docker-compose.yml up -d crosshub-python-worker 2>/dev/null || echo 'python-worker skipped (image missing)'`,
    `sleep 3`,
    `docker ps --filter name=crosshub --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'`,
    `if docker inspect crosshub-python-worker >/dev/null 2>&1; then`,
    `  test "$(docker inspect -f '{{.State.Running}}' crosshub-python-worker)" = "true"`,
    `  docker exec crosshub-python-worker test -d /data`,
    `  docker exec crosshub-python-worker test -d /evidence`,
    `  docker exec crosshub-python-worker test -d /reports`,
    `  docker exec crosshub-python-worker rm -rf /tmp/monitor-smoke`,
    `  docker exec crosshub-python-worker python smoke_monitor_snapshot.py --work-dir /tmp/monitor-smoke`,
    `else`,
    `  echo 'skip_python_worker_smoke=container_missing'`,
    `fi`,
    `if [ -f ${REMOTE_ROOT}/.monitor-smoke.env ]; then`,
    `  set -a`,
    `  . ${REMOTE_ROOT}/.monitor-smoke.env`,
    `  set +a`,
    `  docker run --rm --network host -v ${REMOTE_ROOT}/scripts:/scripts:ro -v ${REMOTE_ROOT}/evidence:${REMOTE_ROOT}/evidence node:20-alpine node /scripts/monitor-api-smoke.js --base-url http://127.0.0.1:18080 --evidence-root ${REMOTE_ROOT}/evidence --db-path ${REMOTE_ROOT}/data/crosshub.db --no-local-worker --timeout-ms 60000`,
    `else`,
    `  echo 'skip_remote_monitor_api_smoke=missing_env_file'`,
    `fi`,
    `curl -s -o /dev/null -w 'java_health=%{http_code}\\n' http://127.0.0.1:18080/api/temu/shops || true`,
    `curl -s http://127.0.0.1:18081/api/health || true`,
    `docker exec 1Panel-openresty-UN3Y openresty -t 2>/dev/null || nginx -t`,
    `docker exec 1Panel-openresty-UN3Y openresty -s reload 2>/dev/null || nginx -s reload`,
    `curl -s -o /dev/null -w 'public_crosshub=%{http_code}\\n' https://www.yoto.work/crosshub/`,
    `curl -s -o /dev/null -w 'public_java=%{http_code}\\n' https://www.yoto.work/api/health`,
  ].join('\n');

  console.log('==> remote docker + nginx reload');
  await exec(conn, remoteCmd);
  conn.end();
  console.log('==> deploy done');
  console.log('  https://www.yoto.work/crosshub/');
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
