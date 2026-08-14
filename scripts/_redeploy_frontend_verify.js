/**
 * Re-upload vue dist and verify remote index.html hash.
 * CROSSHUB_SSH_PASSWORD=... node scripts/_redeploy_frontend_verify.js
 */
const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')

const ROOT = path.resolve(__dirname, '..')
module.paths.push(path.join(__dirname, 'node_modules'))
const { Client } = require('ssh2')

const WEB_ROOT = '/opt/1panel/www/sites/www.yoto.work/index/crosshub'
const ALT_ROOT = '/www/sites/www.yoto.work/index/crosshub'
const host = process.env.CROSSHUB_SSH_HOST || '124.223.27.98'
const password = process.env.CROSSHUB_SSH_PASSWORD
if (!password) {
  console.error('CROSSHUB_SSH_PASSWORD required')
  process.exit(1)
}

function walk(dir, files = []) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name)
    if (fs.statSync(p).isDirectory()) walk(p, files)
    else files.push(p)
  }
  return files
}

function sftpMkdir(sftp, remoteDir) {
  return new Promise((resolve, reject) => {
    sftp.mkdir(remoteDir, { mode: 0o755 }, (err) => {
      if (!err || err.code === 4) return resolve()
      reject(err)
    })
  })
}

async function sftpEnsureDir(sftp, remoteDir) {
  const parts = remoteDir.split('/').filter(Boolean)
  let cur = ''
  for (const part of parts) {
    cur += `/${part}`
    await sftpMkdir(sftp, cur)
  }
}

function sftpPut(sftp, local, remote) {
  return new Promise((resolve, reject) => {
    sftp.fastPut(local, remote, { mode: 0o644 }, (err) => (err ? reject(err) : resolve()))
  })
}

function exec(conn, cmd) {
  return new Promise((resolve, reject) => {
    conn.exec(cmd, (err, stream) => {
      if (err) return reject(err)
      let out = ''
      stream.on('data', (d) => {
        process.stdout.write(d)
        out += d
      })
      stream.stderr.on('data', (d) => process.stderr.write(d))
      stream.on('close', (code) => (code ? reject(new Error(`exit ${code}`)) : resolve(out)))
    })
  })
}

async function uploadTree(sftp, localDir, remoteDir) {
  const files = walk(localDir)
  console.log(`==> upload ${files.length} files -> ${remoteDir}`)
  for (const local of files) {
    const rel = path.relative(localDir, local).replace(/\\/g, '/')
    const remote = `${remoteDir}/${rel}`
    await sftpEnsureDir(sftp, path.posix.dirname(remote))
    await sftpPut(sftp, local, remote)
  }
}

async function main() {
  const webDir = path.join(ROOT, 'dev/vue-site')
  console.log('==> npm run build')
  execSync('npm run build', { cwd: webDir, stdio: 'inherit', shell: true })
  const dist = path.join(webDir, 'dist')
  const localHtml = fs.readFileSync(path.join(dist, 'index.html'), 'utf8')
  const m = localHtml.match(/assets\/(index-[^"]+\.js)/)
  if (!m) throw new Error('local index missing asset hash')
  const expected = m[1]
  console.log('local index asset =', expected)

  const conn = new Client()
  await new Promise((resolve, reject) => conn.on('ready', resolve).on('error', reject).connect({
    host,
    username: process.env.CROSSHUB_SSH_USER || 'root',
    password,
    readyTimeout: 120000,
  }))
  const sftp = await new Promise((resolve, reject) => conn.sftp((e, s) => (e ? reject(e) : resolve(s))))

  await uploadTree(sftp, dist, WEB_ROOT)

  // If /www is a separate tree (not the same inode), mirror there too.
  const check = await exec(
    conn,
    `set -e; echo OPT=$(readlink -f ${WEB_ROOT}/index.html 2>/dev/null || echo missing); echo WWW=$(readlink -f ${ALT_ROOT}/index.html 2>/dev/null || echo missing); ls -la ${WEB_ROOT}/index.html; grep -o 'index-[^"]*\\.js' ${WEB_ROOT}/index.html; test -f ${WEB_ROOT}/assets/${expected} && echo ASSET_OK=${expected} || echo ASSET_MISSING=${expected}; ls -la ${WEB_ROOT}/assets/${expected}`,
  )
  if (!String(check).includes(`ASSET_OK=${expected}`)) {
    throw new Error(`upload verify failed for ${expected}`)
  }

  // Mirror to /www if it exists and differs
  const same = await exec(
    conn,
    `if [ -d "$(dirname ${ALT_ROOT})" ]; then
       OPT_INO=$(stat -c %i ${WEB_ROOT}/index.html 2>/dev/null || echo 0)
       WWW_INO=$(stat -c %i ${ALT_ROOT}/index.html 2>/dev/null || echo 0)
       echo OPT_INO=$OPT_INO WWW_INO=$WWW_INO
       if [ "$WWW_INO" != "0" ] && [ "$OPT_INO" != "$WWW_INO" ]; then
         echo MIRROR_NEEDED=1
       else
         echo MIRROR_NEEDED=0
       fi
     else
       echo MIRROR_NEEDED=0
     fi`,
  )
  if (String(same).includes('MIRROR_NEEDED=1')) {
    console.log('==> mirroring to /www path')
    await uploadTree(sftp, dist, ALT_ROOT)
  }

  await exec(
    conn,
    `docker exec 1Panel-openresty-UN3Y openresty -s reload 2>/dev/null || nginx -s reload || true; curl -s https://www.yoto.work/crosshub/ | grep -o 'index-[^"]*\\.js' | head -1`,
  )
  conn.end()
  console.log('==> frontend redeploy verified')
}

main().catch((e) => {
  console.error(e.message || e)
  process.exit(1)
})
