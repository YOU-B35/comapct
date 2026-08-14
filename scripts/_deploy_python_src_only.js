/**
 * Upload backend/python -> /data/crosshub/python-src (skip browser profiles/caches).
 * CROSSHUB_SSH_PASSWORD=... node scripts/_deploy_python_src_only.js
 */
const fs = require('fs')
const path = require('path')

const ROOT = path.resolve(__dirname, '..')
module.paths.push(path.join(__dirname, 'node_modules'))
const { Client } = require('ssh2')

const REMOTE = '/data/crosshub/python-src'
const LOCAL = path.join(ROOT, 'backend/python')
const host = process.env.CROSSHUB_SSH_HOST || '124.223.27.98'
const password = process.env.CROSSHUB_SSH_PASSWORD
if (!password) {
  console.error('CROSSHUB_SSH_PASSWORD required')
  process.exit(1)
}

function shouldSkip(name, rel) {
  const parts = rel.split('/').filter(Boolean)
  const skipNames = new Set([
    '.temu-browser-profile',
    '.aliexpress-browser-profile',
    '.amazon-browser-profile',
    '.douyin-browser-profile',
    '.sync-helper-local',
    'helper_app',
    'exports',
    'reports',
    '.pytest_cache',
    '__pycache__',
    'Cache',
    'Code Cache',
    'GPUCache',
    'tests',
    '.env',
  ])
  if (skipNames.has(name)) return true
  if (parts.some((p) => skipNames.has(p))) return true
  if (rel.endsWith('.pyc')) return true
  return false
}

function walk(dir, files = [], baseDir = dir) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name)
    const rel = path.relative(baseDir, p).replace(/\\/g, '/')
    if (shouldSkip(name, rel)) continue
    if (fs.statSync(p).isDirectory()) walk(p, files, baseDir)
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

async function main() {
  const files = walk(LOCAL)
  console.log(`==> uploading ${files.length} python files to ${REMOTE}`)

  const conn = new Client()
  await new Promise((resolve, reject) =>
    conn.on('ready', resolve).on('error', reject).connect({
      host,
      username: process.env.CROSSHUB_SSH_USER || 'root',
      password,
      readyTimeout: 120000,
    }),
  )
  const sftp = await new Promise((resolve, reject) =>
    conn.sftp((e, s) => (e ? reject(e) : resolve(s))),
  )

  await sftpEnsureDir(sftp, REMOTE)
  let n = 0
  for (const local of files) {
    const rel = path.relative(LOCAL, local).replace(/\\/g, '/')
    const remote = `${REMOTE}/${rel}`
    await sftpEnsureDir(sftp, path.posix.dirname(remote))
    await sftpPut(sftp, local, remote)
    n += 1
    if (n % 50 === 0) console.log(`  uploaded ${n}/${files.length}`)
  }
  console.log(`==> uploaded ${n} files`)

  await exec(
    conn,
    [
      'set -e',
      `test -f ${REMOTE}/app/browser/temu_cookie_trust.py`,
      `test -f ${REMOTE}/app/browser/profile_startup.py`,
      `test -f ${REMOTE}/seller_session_status.py`,
      `test -f ${REMOTE}/app/browser/profile_lock.py`,
      `ls -la ${REMOTE}/app/browser/temu_cookie_trust.py ${REMOTE}/app/browser/profile_startup.py`,
      // refresh java mount visibility is instant (bind mount); restart optional
      'docker inspect -f "{{.State.Running}}" crosshub-java',
      'echo python_src_deploy_ok',
    ].join('\n'),
  )

  conn.end()
  console.log('==> done')
}

main().catch((e) => {
  console.error(e.message || e)
  process.exit(1)
})
