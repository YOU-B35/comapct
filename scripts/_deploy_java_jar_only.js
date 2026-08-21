const path = require('path')
module.paths.push(path.join(__dirname, 'node_modules'))
const { Client } = require('ssh2')
const fs = require('fs')

const host = process.env.CROSSHUB_SSH_HOST || '124.223.27.98'
const password = process.env.CROSSHUB_SSH_PASSWORD || ''
const keyPath = process.env.CROSSHUB_SSH_KEY || ''
if (!password && !keyPath) {
  console.error('CROSSHUB_SSH_PASSWORD or CROSSHUB_SSH_KEY required')
  process.exit(1)
}

const local = path.join(__dirname, '..', 'backend', 'java', 'target', 'temu-api-0.1.0.jar')
const remoteRoot = '/data/crosshub'
const conn = new Client()
const ssh = {
  host,
  port: Number(process.env.CROSSHUB_SSH_PORT || 22),
  username: process.env.CROSSHUB_SSH_USER || 'root',
  readyTimeout: 120000,
};
if (password) ssh.password = password;
if (keyPath) ssh.privateKey = fs.readFileSync(keyPath);

conn
  .on('ready', () => {
    conn.sftp((err, sftp) => {
      if (err) {
        console.error(err)
        process.exit(1)
      }
      console.log('upload jar', fs.statSync(local).size)
      sftp.fastPut(local, `${remoteRoot}/app.jar`, (putErr) => {
        if (putErr) {
          console.error(putErr)
          process.exit(1)
        }
        console.log('uploaded to', `${remoteRoot}/app.jar`)
        const cmd = [
          'set -e',
          `cd ${remoteRoot}`,
          'docker build -f Dockerfile.java -t crosshub-java:latest .',
          'docker compose -f docker-compose.yml up -d --force-recreate crosshub-java',
          'sleep 5',
          "curl -s -o /dev/null -w 'java_health=%{http_code}\\n' http://127.0.0.1:18080/api/health || true",
          'docker ps --filter name=crosshub-java --format "{{.Names}} {{.Status}}"',
        ].join('\n')
        conn.exec(cmd, (execErr, stream) => {
          if (execErr) {
            console.error(execErr)
            process.exit(1)
          }
          stream.on('data', (d) => process.stdout.write(d))
          stream.stderr.on('data', (d) => process.stderr.write(d))
          stream.on('close', (code) => {
            conn.end()
            process.exit(code || 0)
          })
        })
      })
    })
  })
  .on('error', (e) => {
    console.error(e.message || e)
    process.exit(1)
  })
  .connect(ssh)
