/**
 * Upload docker-compose.yml (with commander env_file) and recreate crosshub-java.
 * CROSSHUB_SSH_PASSWORD=... node scripts/_fix_commander_env_compose.js
 */
const fs = require('fs')
const path = require('path')

const ROOT = path.resolve(__dirname, '..')
module.paths.push(path.join(__dirname, 'node_modules'))
const { Client } = require('ssh2')

const host = process.env.CROSSHUB_SSH_HOST || '124.223.27.98'
const password = process.env.CROSSHUB_SSH_PASSWORD
if (!password) {
  console.error('CROSSHUB_SSH_PASSWORD required')
  process.exit(1)
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
      stream.on('close', (code) => (code ? reject(new Error(`exit ${code}: ${out}`)) : resolve(out)))
    })
  })
}

async function main() {
  const localCompose = path.join(ROOT, 'deploy/docker-compose.yml')
  const remoteCompose = '/data/crosshub/docker-compose.yml'
  const composeBody = fs.readFileSync(localCompose, 'utf8')
  if (!composeBody.includes('env_file:') || !composeBody.includes('.commander.env')) {
    throw new Error('local docker-compose.yml missing env_file .commander.env')
  }

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

  console.log('==> upload docker-compose.yml')
  await sftpPut(sftp, localCompose, remoteCompose)

  console.log('==> recreate crosshub-java with commander env')
  await exec(
    conn,
    [
      'set -e',
      'test -f /data/crosshub/.commander.env',
      // ensure no blank required keys
      'grep -q "^CROSSHUB_COMMANDER_USERNAME=." /data/crosshub/.commander.env',
      'grep -q "^CROSSHUB_COMMANDER_PASSWORD=." /data/crosshub/.commander.env',
      'cd /data/crosshub',
      'docker compose -f docker-compose.yml up -d --force-recreate crosshub-java',
      'sleep 8',
      'docker exec crosshub-java printenv | grep -E "^CROSSHUB_COMMANDER_(BASE_URL|USERNAME)=" | sed "s/=.*/=SET/"',
      'docker logs crosshub-java 2>&1 | grep -i commander | tail -5',
      'curl -s -o /dev/null -w "java_health=%{http_code}\\n" http://127.0.0.1:18080/api/health || true',
      'echo commander_env_fix_ok',
    ].join('\n'),
  )

  conn.end()
  console.log('==> done')
}

main().catch((e) => {
  console.error(e.message || e)
  process.exit(1)
})
