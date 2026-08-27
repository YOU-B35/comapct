/**
 * Fast remainder of the ubuntu deploy: uploads tgz bundles, extracts with sudo,
 * rebuilds docker containers and reloads nginx. Pairs with _deploy_server_ubuntu.js
 * (which already built the jar/dist and staged small files).
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
module.paths.push(path.join(__dirname, 'node_modules'));

const REMOTE_ROOT = '/data/crosshub';
const WEB_ROOT = '/opt/1panel/www/sites/www.yoto.work/index/crosshub';
const PROXY_CONF = '/opt/1panel/www/sites/www.yoto.work/proxy/crosshub.conf';
const STAGE = '/home/ubuntu/crosshub-deploy-stage';

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

function sftpPut(sftp, local, remote) {
  return new Promise((resolve, reject) => {
    sftp.fastPut(local, remote, { mode: 0o644 }, (err) => (err ? reject(err) : resolve()));
  });
}

async function main() {
  const { Client } = require('ssh2');
  const localJarSize = fs.statSync(path.join(ROOT, 'deploy/.build/app.jar')).size;

  const conn = new Client();
  await new Promise((resolve, reject) => {
    conn.on('ready', resolve).on('error', reject).connect({
      host: process.env.CROSSHUB_SSH_HOST,
      port: Number(process.env.CROSSHUB_SSH_PORT || 22),
      username: process.env.CROSSHUB_SSH_USER || 'ubuntu',
      password: process.env.CROSSHUB_SSH_PASSWORD,
      readyTimeout: 120000,
    });
  });

  const jarStat = await exec(conn, `stat -c %s ${STAGE}/app.jar || echo missing`);
  if (String(jarStat).trim() !== String(localJarSize)) {
    console.log(`==> app.jar mismatch/missing (remote ${jarStat.trim()} vs local ${localJarSize}); re-uploading`);
    const sftp0 = await new Promise((r, j) => conn.sftp((e, s) => (e ? j(e) : r(s))));
    await sftpPut(sftp0, path.join(ROOT, 'deploy/.build/app.jar'), `${STAGE}/app.jar`);
  } else {
    console.log(`==> app.jar already staged (${localJarSize} bytes)`);
  }

  console.log('==> upload tar bundles');
  const sftp = await new Promise((r, j) => conn.sftp((e, s) => (e ? j(e) : r(s))));
  await sftpPut(sftp, path.join(ROOT, 'deploy/.build/python-src.tgz'), `${STAGE}/python-src.tgz`);
  await sftpPut(sftp, path.join(ROOT, 'deploy/.build/web.tgz'), `${STAGE}/web.tgz`);
  console.log('==> bundles uploaded');

  const remoteCmd = [
    'set -e',
    `sudo mkdir -p ${REMOTE_ROOT}/data ${REMOTE_ROOT}/evidence ${REMOTE_ROOT}/reports ${WEB_ROOT}`,
    `sudo cp ${STAGE}/app.jar ${STAGE}/Dockerfile.java ${STAGE}/Dockerfile.express ${STAGE}/Dockerfile.python-worker ${STAGE}/docker-compose.yml ${REMOTE_ROOT}/`,
    `[ -f ${STAGE}/crosshub.db ] && sudo mkdir -p ${REMOTE_ROOT}/data && sudo cp ${STAGE}/crosshub.db ${REMOTE_ROOT}/data/crosshub.db || true`,
    `sudo mkdir -p ${REMOTE_ROOT}/scripts && sudo cp ${STAGE}/scripts/monitor-api-smoke.js ${REMOTE_ROOT}/scripts/monitor-api-smoke.js`,
    `sudo mkdir -p ${REMOTE_ROOT}/express-src && sudo cp -a ${STAGE}/express-src/. ${REMOTE_ROOT}/express-src/`,
    // python-src: overlay only — server-side .env must survive; stale files are kept (same as original uploadTree)
    `rm -rf /tmp/pysrc && mkdir -p /tmp/pysrc && tar xzf ${STAGE}/python-src.tgz -C /tmp/pysrc --strip-components=2`,
    `sudo mkdir -p ${REMOTE_ROOT}/python-src && sudo cp -a /tmp/pysrc/. ${REMOTE_ROOT}/python-src/`,
    // web: clean everything except downloads/ and old backups, then copy new dist
    `rm -rf /tmp/webstage && mkdir -p /tmp/webstage && tar xzf ${STAGE}/web.tgz -C /tmp/webstage --strip-components=3`,
    `sudo find ${WEB_ROOT} -mindepth 1 -maxdepth 1 ! -name downloads ! -name 'index.html.bak.*' -exec rm -rf {} +`,
    `sudo cp -a /tmp/webstage/. ${WEB_ROOT}/`,
    `sudo chown -R root:root ${WEB_ROOT}`,
    `sudo cp ${STAGE}/crosshub-proxy.conf ${PROXY_CONF}`,
    `cd ${REMOTE_ROOT}`,
    `echo '== docker build java =='`,
    `sudo docker build -f Dockerfile.java -t crosshub-java:latest .`,
    `echo '== docker build express =='`,
    `sudo docker build -f Dockerfile.express -t crosshub-express:latest express-src`,
    `sudo docker compose -f docker-compose.yml up -d --force-recreate crosshub-java crosshub-express`,
    `sudo docker compose -f docker-compose.yml up -d crosshub-python-worker 2>/dev/null || echo 'python-worker skipped (image missing)'`,
    `sleep 3`,
    `sudo docker ps --filter name=crosshub --format 'table {{.Names}}\\t{{.Ports}}\\t{{.Status}}'`,
    `curl -s -o /dev/null -w 'java_health=%{http_code}\\n' http://127.0.0.1:18080/api/temu/shops || true`,
    `curl -s http://127.0.0.1:18081/api/health || true`,
    `sudo docker exec 1Panel-openresty-UN3Y openresty -t`,
    `sudo docker exec 1Panel-openresty-UN3Y openresty -s reload`,
    `curl -s -o /dev/null -w 'public_crosshub=%{http_code}\\n' https://www.yoto.work/crosshub/`,
    `curl -s -o /dev/null -w 'public_java=%{http_code}\\n' https://www.yoto.work/api/health`,
    `rm -rf /tmp/pysrc /tmp/webstage`,
  ].join('\n');

  console.log('==> remote sync + docker + nginx');
  await exec(conn, remoteCmd);
  conn.end();
  console.log('==> deploy done');
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
