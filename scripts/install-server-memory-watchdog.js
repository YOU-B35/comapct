/**
 * Install host memory watchdog + soft docker memory limits on production.
 * CROSSHUB_SSH_PASSWORD=... node scripts/install-server-memory-watchdog.js
 */
const fs = require('fs')
const path = require('path')
module.paths.push(path.join(__dirname, 'node_modules'))
const { Client } = require('ssh2')

const password = process.env.CROSSHUB_SSH_PASSWORD
if (!password) {
  console.error('CROSSHUB_SSH_PASSWORD required')
  process.exit(1)
}

const localScript = path.join(__dirname, 'server-memory-watchdog.sh')
const remoteScript = '/usr/local/sbin/crosshub-memory-watchdog.sh'
const cronPath = '/etc/cron.d/crosshub-memory-watchdog'

function exec(conn, cmd) {
  return new Promise((resolve, reject) => {
    conn.exec(cmd, (err, stream) => {
      if (err) return reject(err)
      let out = ''
      stream.on('data', (d) => {
        out += d
        process.stdout.write(d)
      })
      stream.stderr.on('data', (d) => {
        out += d
        process.stderr.write(d)
      })
      stream.on('close', (code) => (code ? reject(new Error(`exit ${code}\n${out}`)) : resolve(out)))
    })
  })
}

function sftpPut(sftp, local, remote, mode = 0o755) {
  return new Promise((resolve, reject) => {
    sftp.fastPut(local, remote, { mode }, (err) => (err ? reject(err) : resolve()))
  })
}

async function main() {
  if (!fs.existsSync(localScript)) throw new Error(`missing ${localScript}`)

  const conn = new Client()
  await new Promise((resolve, reject) => {
    conn
      .on('ready', resolve)
      .on('error', reject)
      .connect({
        host: process.env.CROSSHUB_SSH_HOST || '124.223.27.98',
        username: process.env.CROSSHUB_SSH_USER || 'root',
        password,
        readyTimeout: 90000,
      })
  })
  const sftp = await new Promise((resolve, reject) => {
    conn.sftp((e, s) => (e ? reject(e) : resolve(s)))
  })

  console.log('==> upload watchdog')
  await sftpPut(sftp, localScript, remoteScript, 0o755)
  await exec(conn, `sed -i 's/\\r$//' ${remoteScript} && chmod 755 ${remoteScript}`)

  const cronBody = `# CrossHub host memory watchdog — every minute\nSHELL=/bin/bash\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n* * * * * root ${remoteScript}\n`
  const tmpCron = path.join(__dirname, '.build-watchdog.cron')
  fs.mkdirSync(path.dirname(tmpCron), { recursive: true })
  fs.writeFileSync(tmpCron, cronBody, 'utf8')
  await sftpPut(sftp, tmpCron, cronPath, 0o644)
  await exec(conn, `sed -i 's/\\r$//' ${cronPath} && chmod 644 ${cronPath}`)

  console.log('==> apply soft memory limits (runtime, survives until recreate)')
  // Commander historically pegs CPU/RAM; AutoMedia currently ~1GiB
  await exec(
    conn,
    [
      'set -e',
      'docker update --memory=768m --memory-swap=1024m --cpus=1.5 commander-server-t260220 || true',
      'docker update --memory=1280m --memory-swap=1536m --cpus=1.5 automedia-social-auto-upload || true',
      'docker update --memory=768m --memory-swap=1024m --cpus=1.5 crosshub-java || true',
      'echo "=== limits ==="',
      'docker inspect -f "{{.Name}} mem={{.HostConfig.Memory}} swap={{.HostConfig.MemorySwap}} cpus={{.HostConfig.NanoCpus}}" commander-server-t260220 automedia-social-auto-upload crosshub-java',
    ].join('\n'),
  )

  console.log('==> stop confirmed-idle containers')
  await exec(
    conn,
    [
      'set +e',
      'docker update --restart=no 1Panel-openlist-SSrO || true',
      'docker stop 1Panel-openlist-SSrO || true',
      'docker inspect -f "{{.Name}} running={{.State.Running}} restart={{.HostConfig.RestartPolicy.Name}}" 1Panel-openlist-SSrO || true',
    ].join('\n'),
  )

  console.log('==> run once + show status')
  await exec(
    conn,
    [
      'set +e',
      remoteScript,
      'echo "=== last log ==="',
      'tail -n 20 /var/log/crosshub-watchdog/watchdog.log',
      'echo "=== free ==="',
      'free -h',
      'echo "=== cron ==="',
      `ls -l ${cronPath}`,
      `crontab -l 2>/dev/null | head || true`,
    ].join('\n'),
  )

  conn.end()
  console.log('==> watchdog installed')
}

main().catch((e) => {
  console.error(e.message || e)
  process.exit(1)
})
