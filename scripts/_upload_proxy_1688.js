const fs = require('fs')
const path = require('path')
module.paths.push(path.join(__dirname, 'node_modules'))
const { Client } = require('ssh2')

const ROOT = path.resolve(__dirname, '..')
const LOCAL_PROXY = path.join(ROOT, 'deploy', 'crosshub-proxy.conf')
const REMOTE_DATA = '/data/crosshub/crosshub-proxy.conf'
const REMOTE_PROXY = '/opt/1panel/www/sites/www.yoto.work/proxy/crosshub.conf'

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

function sftpPut(sftp, local, remote) {
  return new Promise((resolve, reject) => {
    sftp.fastPut(local, remote, { mode: 0o644 }, (err) => (err ? reject(err) : resolve()))
  })
}

async function main() {
  const conn = new Client()
  await new Promise((resolve, reject) => {
    conn.on('ready', resolve).on('error', reject).connect({
      host: process.env.CROSSHUB_SSH_HOST || '124.223.27.98',
      username: process.env.CROSSHUB_SSH_USER || 'root',
      password: process.env.CROSSHUB_SSH_PASSWORD || '',
      readyTimeout: 60000,
    })
  })
  const sftp = await new Promise((resolve, reject) => {
    conn.sftp((err, s) => (err ? reject(err) : resolve(s)))
  })
  console.log('==> upload proxy conf')
  await sftpPut(sftp, LOCAL_PROXY, REMOTE_DATA)
  await sftpPut(sftp, LOCAL_PROXY, REMOTE_PROXY)
  await exec(
    conn,
    [
      `grep -n "api/1688" ${REMOTE_PROXY}`,
      'sleep 2',
      'curl -s -o /dev/null -w "local_java_shops=%{http_code}\\n" http://127.0.0.1:18080/api/temu/shops || true',
      'curl -s -o /dev/null -w "local_java_1688=%{http_code}\\n" http://127.0.0.1:18080/api/1688/session || true',
      'docker exec 1Panel-openresty-UN3Y openresty -t',
      'docker exec 1Panel-openresty-UN3Y openresty -s reload',
      'curl -s -o /dev/null -w "public_1688=%{http_code}\\n" https://www.yoto.work/api/1688/session',
      'curl -s -o /dev/null -w "public_health=%{http_code}\\n" https://www.yoto.work/api/health',
      'curl -s -o /dev/null -w "helper_zip=%{http_code}\\n" https://www.yoto.work/crosshub/downloads/CrossHub-Sync-Helper.zip',
      'curl -s -o /dev/null -w "crosshub=%{http_code}\\n" https://www.yoto.work/crosshub/',
      'ls /opt/1panel/www/sites/www.yoto.work/index/crosshub/assets/HelperOpsGuideDialog*.js 2>/dev/null | tail -3',
      'docker ps --filter name=crosshub --format "table {{.Names}}\\t{{.Status}}"',
    ].join('\n'),
  )
  conn.end()
  console.log('==> done')
}

main().catch((e) => {
  console.error(e.message || e)
  process.exit(1)
})
