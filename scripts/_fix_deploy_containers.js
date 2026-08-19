const path = require('path')
module.paths.push(path.join(__dirname, 'node_modules'))
const { Client } = require('ssh2')

const conn = new Client()
const cmd = [
  'set -e',
  'cd /data/crosshub',
  'cp /data/crosshub/crosshub-proxy.conf /opt/1panel/www/sites/www.yoto.work/proxy/crosshub.conf',
  'docker rm -f crosshub-java crosshub-express 2>/dev/null || true',
  'docker ps -aq --filter name=crosshub-express | xargs -r docker rm -f',
  'docker ps -aq --filter name=crosshub-java | xargs -r docker rm -f',
  'docker compose -f docker-compose.yml up -d --force-recreate crosshub-java crosshub-express',
  'sleep 5',
  'docker ps --filter name=crosshub --format "table {{.Names}}\\t{{.Ports}}\\t{{.Status}}"',
  'curl -s -o /dev/null -w "java=%{http_code}\\n" http://127.0.0.1:18080/api/temu/shops || true',
  'curl -s http://127.0.0.1:18081/api/health || true',
  'docker exec 1Panel-openresty-UN3Y openresty -t 2>/dev/null || nginx -t',
  'docker exec 1Panel-openresty-UN3Y openresty -s reload 2>/dev/null || nginx -s reload',
  'curl -s -o /dev/null -w "public_crosshub=%{http_code}\\n" https://www.yoto.work/crosshub/',
  'curl -s -o /dev/null -w "public_1688=%{http_code}\\n" https://www.yoto.work/api/1688/session',
  'curl -s -o /dev/null -w "helper_zip=%{http_code}\\n" https://www.yoto.work/crosshub/downloads/CrossHub-Sync-Helper.zip',
  'ls -lh /opt/1panel/www/sites/www.yoto.work/index/crosshub/downloads/CrossHub-Sync-Helper.zip 2>/dev/null || echo missing_helper_zip',
  'grep -n "api/1688" /opt/1panel/www/sites/www.yoto.work/proxy/crosshub.conf | head',
].join('\n')

conn
  .on('ready', () => {
    conn.exec(cmd, (err, stream) => {
      if (err) {
        console.error(err)
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
  .on('error', (e) => {
    console.error(e)
    process.exit(1)
  })
  .connect({
    host: process.env.CROSSHUB_SSH_HOST || '124.223.27.98',
    username: process.env.CROSSHUB_SSH_USER || 'root',
    password: process.env.CROSSHUB_SSH_PASSWORD || '',
    readyTimeout: 120000,
  })
