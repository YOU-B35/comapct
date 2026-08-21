/** 仅重新构建并上传前端静态资源 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
module.paths.push(path.join(__dirname, 'node_modules'));
const { Client } = require('ssh2');

const WEB_ROOT = '/opt/1panel/www/sites/www.yoto.work/index/crosshub';
const SSH = {
  host: process.env.CROSSHUB_SSH_HOST || '',
  port: Number(process.env.CROSSHUB_SSH_PORT || 22),
  username: process.env.CROSSHUB_SSH_USER || 'root',
  password: process.env.CROSSHUB_SSH_PASSWORD || '',
  readyTimeout: 120000,
};
const keyPath = process.env.CROSSHUB_SSH_KEY || '';
if (keyPath && fs.existsSync(keyPath)) {
  SSH.privateKey = fs.readFileSync(keyPath);
}

if (!SSH.host || (!SSH.password && !SSH.privateKey)) {
  console.error('Set CROSSHUB_SSH_HOST and CROSSHUB_SSH_PASSWORD/CROSSHUB_SSH_KEY before deploying.');
  process.exit(1);
}

function walk(dir, files = []) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    if (fs.statSync(p).isDirectory()) walk(p, files);
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

async function main() {
  const webDir = path.join(ROOT, 'dev/vue-site');
  console.log('==> npm run build');
  execSync('npm run build', { cwd: webDir, stdio: 'inherit', shell: true });

  const dist = path.join(webDir, 'dist');
  const html = fs.readFileSync(path.join(dist, 'index.html'), 'utf8');
  if (!html.includes('/crosshub/assets/')) {
    throw new Error('build still missing /crosshub/ base path in index.html');
  }
  console.log('  index.html asset prefix OK');

  const conn = new Client();
  await new Promise((resolve, reject) => conn.on('ready', resolve).on('error', reject).connect(SSH));
  const sftp = await new Promise((resolve, reject) => conn.sftp((e, s) => (e ? reject(e) : resolve(s))));

  const files = walk(dist);
  console.log(`==> upload ${files.length} files`);
  for (const local of files) {
    const rel = path.relative(dist, local).replace(/\\/g, '/');
    const remote = `${WEB_ROOT}/${rel}`;
    await sftpEnsureDir(sftp, path.posix.dirname(remote));
    await sftpPut(sftp, local, remote);
  }

  await new Promise((resolve, reject) => {
    conn.exec(
      `head -14 ${WEB_ROOT}/index.html; curl -s -o /dev/null -w "\\njs=%{http_code}\\n" https://www.yoto.work/crosshub/assets/$(basename $(grep -o '/crosshub/assets/[^"]*\\.js' ${WEB_ROOT}/index.html | head -1))`,
      (err, stream) => {
        stream.on('data', (d) => process.stdout.write(d));
        stream.on('close', (code) => { conn.end(); code ? reject(new Error(`exit ${code}`)) : resolve(); });
      },
    );
  });
  console.log('==> done: https://www.yoto.work/crosshub/');
}

main().catch((e) => { console.error(e.message || e); process.exit(1); });
