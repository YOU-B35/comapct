/* Upload Sync Helper zip as `ubuntu` user: SFTP to staging then sudo mv into
 * /opt/1panel/www/sites/www.yoto.work/index/crosshub/downloads/ (root-owned).
 * Usage: CROSSHUB_SSH_HOST=... CROSSHUB_SSH_PASSWORD=... node scripts/_upload_helper_zip_ubuntu.js
 */
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
module.paths.push(path.join(__dirname, 'node_modules'));
const { Client } = require('ssh2');

const LOCAL_ZIP =
  process.env.CROSSHUB_HELPER_ZIP ||
  path.join(ROOT, 'dist', 'CrossHub-Sync-Helper.zip');
const REMOTE_DIR = '/opt/1panel/www/sites/www.yoto.work/index/crosshub/downloads';
const REMOTE_ZIP = `${REMOTE_DIR}/CrossHub-Sync-Helper.zip`;
const STAGE = '/home/ubuntu/CrossHub-Sync-Helper.zip.stage';

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
  const host = process.env.CROSSHUB_SSH_HOST;
  const password = process.env.CROSSHUB_SSH_PASSWORD;
  if (!host || !password) throw new Error('CROSSHUB_SSH_HOST / CROSSHUB_SSH_PASSWORD required');
  if (!fs.existsSync(LOCAL_ZIP)) throw new Error(`missing zip: ${LOCAL_ZIP}`);

  const sizeMb = (fs.statSync(LOCAL_ZIP).size / 1024 / 1024).toFixed(1);
  console.log(`==> upload ${LOCAL_ZIP} (${sizeMb} MB) -> staging`);
  const conn = new Client();
  await new Promise((resolve, reject) => {
    conn.on('ready', resolve).on('error', reject).connect({
      host,
      port: Number(process.env.CROSSHUB_SSH_PORT || 22),
      username: process.env.CROSSHUB_SSH_USER || 'ubuntu',
      password,
      readyTimeout: 120000,
    });
  });

  // keep the previous version for rollback if present
  await exec(conn, [
    `set -e`,
    `[ -f ${REMOTE_ZIP} ] && sudo cp ${REMOTE_ZIP} ${REMOTE_ZIP}.bak.$(date +%Y%m%d_%H%M%S) || true`,
    `rm -f ${STAGE}`,
  ].join('\n'));

  const sftp = await new Promise((resolve, reject) => {
    conn.sftp((err, s) => (err ? reject(err) : resolve(s)));
  });
  await sftpPut(sftp, LOCAL_ZIP, STAGE);

  console.log('==> move into downloads dir');
  await exec(conn, [
    `set -e`,
    `sudo mkdir -p ${REMOTE_DIR}`,
    `sudo mv ${STAGE} ${REMOTE_ZIP}`,
    `sudo chown root:root ${REMOTE_ZIP}`,
    `ls -lh ${REMOTE_DIR}/ | tail -5`,
  ].join('\n'));
  conn.end();
  console.log('==> helper zip uploaded');
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
