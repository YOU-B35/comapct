/**
 * Upload Sync Helper zip to production downloads path.
 * Usage: CROSSHUB_SSH_HOST=... CROSSHUB_SSH_PASSWORD=... node scripts/upload-helper-zip.js
 */
const fs = require('fs')
const path = require('path')

const ROOT = path.resolve(__dirname, '..')
module.paths.push(path.join(__dirname, 'node_modules'))
const { Client } = require('ssh2')

const LOCAL_ZIP =
  process.env.CROSSHUB_HELPER_ZIP ||
  path.join(ROOT, 'dist', 'CrossHub-Sync-Helper.zip')
const REMOTE_DIR = '/opt/1panel/www/sites/www.yoto.work/index/crosshub/downloads'
const REMOTE_ZIP = `${REMOTE_DIR}/CrossHub-Sync-Helper.zip`

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
      stream.on('close', (code) => {
        if (code) reject(new Error(`remote exit ${code}`))
        else resolve(out)
      })
    })
  })
}

function sftpPut(sftp, local, remote) {
  return new Promise((resolve, reject) => {
    sftp.fastPut(local, remote, { mode: 0o644 }, (err) => (err ? reject(err) : resolve()))
  })
}

async function main() {
  const host = process.env.CROSSHUB_SSH_HOST
  const password = process.env.CROSSHUB_SSH_PASSWORD
  if (!host || !password) throw new Error('CROSSHUB_SSH_HOST / CROSSHUB_SSH_PASSWORD required')
  if (!fs.existsSync(LOCAL_ZIP)) throw new Error(`missing zip: ${LOCAL_ZIP}`)

  const sizeMb = (fs.statSync(LOCAL_ZIP).size / 1024 / 1024).toFixed(1)
  console.log(`==> upload ${LOCAL_ZIP} (${sizeMb} MB) -> ${REMOTE_ZIP}`)

  const conn = new Client()
  await new Promise((resolve, reject) => {
    conn.on('ready', resolve).on('error', reject).connect({
      host,
      port: Number(process.env.CROSSHUB_SSH_PORT || 22),
      username: process.env.CROSSHUB_SSH_USER || 'root',
      password,
      readyTimeout: 120000,
    })
  })

  await exec(conn, `mkdir -p ${REMOTE_DIR}`)
  const sftp = await new Promise((resolve, reject) => {
    conn.sftp((err, s) => (err ? reject(err) : resolve(s)))
  })
  await sftpPut(sftp, LOCAL_ZIP, REMOTE_ZIP)
  await exec(
    conn,
    [
      `ls -lh ${REMOTE_ZIP}`,
      `file ${REMOTE_ZIP}`,
      // ensure SPA fallback won't hide real files: downloads should be static
      `test -f ${REMOTE_ZIP}`,
    ].join('\n'),
  )
  conn.end()
  console.log('==> helper zip uploaded')
}

main().catch((e) => {
  console.error(e.message || e)
  process.exit(1)
})
