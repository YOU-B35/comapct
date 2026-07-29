/**
 * Upload vue-site/dist only to production nginx web root.
 * Usage: CROSSHUB_SSH_HOST=... CROSSHUB_SSH_PASSWORD=... node scripts/_upload_frontend_only.js
 */
const path = require('path')
const fs = require('fs')
const ROOT = path.resolve(__dirname, '..')
module.paths.push(path.join(__dirname, 'node_modules'))
const { Client } = require('ssh2')

const distDir = path.join(ROOT, 'dev/vue-site/dist')
const WEB_ROOT = '/opt/1panel/www/sites/www.yoto.work/index/crosshub'

function walk(dir, files = [], baseDir = dir) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name)
    if (fs.statSync(p).isDirectory()) walk(p, files, baseDir)
    else files.push(p)
  }
  return files
}

function sftpMkdir(sftp, remoteDir) {
  return new Promise((resolve, reject) => {
    sftp.mkdir(remoteDir, { mode: 0o755 }, (err) => {
      if (!err || err.code === 4) resolve()
      else reject(err)
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

async function uploadTree(sftp, localDir, remoteDir) {
  await sftpEnsureDir(sftp, remoteDir)
  const files = walk(localDir)
  for (const local of files) {
    const rel = path.relative(localDir, local).replace(/\\/g, '/')
    const remote = `${remoteDir}/${rel}`
    await sftpEnsureDir(sftp, path.posix.dirname(remote))
    await sftpPut(sftp, local, remote)
    process.stdout.write('.')
  }
  console.log(`\nuploaded ${files.length} files`)
}

async function main() {
  if (!fs.existsSync(path.join(distDir, 'index.html'))) {
    throw new Error('missing dist/index.html — run npm run build first')
  }
  const host = process.env.CROSSHUB_SSH_HOST
  const password = process.env.CROSSHUB_SSH_PASSWORD
  if (!host || !password) throw new Error('CROSSHUB_SSH_HOST / CROSSHUB_SSH_PASSWORD required')

  const conn = new Client()
  await new Promise((resolve, reject) => {
    conn.on('ready', resolve).on('error', reject).connect({
      host,
      username: process.env.CROSSHUB_SSH_USER || 'root',
      password,
      readyTimeout: 120000,
    })
  })

  const sftp = await new Promise((resolve, reject) => {
    conn.sftp((err, s) => (err ? reject(err) : resolve(s)))
  })

  console.log('uploading frontend to', WEB_ROOT)
  await uploadTree(sftp, distDir, WEB_ROOT)

  await new Promise((resolve, reject) => {
    conn.exec(
      'curl -s -o /dev/null -w public_crosshub=%{http_code}\\n https://www.yoto.work/crosshub/',
      (err, stream) => {
        if (err) return reject(err)
        stream.on('data', (d) => process.stdout.write(d))
        stream.stderr.on('data', (d) => process.stderr.write(d))
        stream.on('close', (code) => (code ? reject(new Error(`exit ${code}`)) : resolve()))
      },
    )
  })

  conn.end()
  console.log('frontend deploy done')
}

main().catch((e) => {
  console.error(e.message || e)
  process.exit(1)
})
