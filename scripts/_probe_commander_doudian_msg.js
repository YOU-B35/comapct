/**
 * Grep commander-server container / static for 抖店 Agent detection error.
 */
const { Client } = require('ssh2')
const c = new Client()
c.on('ready', () => {
  const cmd = `
set -e
echo '=== search error string on host ==='
grep -RIn --include='*.js' --include='*.vue' --include='*.go' --include='*.html' --include='*.json' -a '没有读取到抖店\\|抖店助手\\|抖店 Agent\\|没有读取到' /opt /data /root 2>/dev/null | head -60 || true
echo '=== commander container ==='
docker ps --filter name=commander --format '{{.Names}} {{.Image}} {{.Status}}'
echo '=== inside commander-server ==='
docker exec commander-server-t260220 sh -c "grep -RIn -a '没有读取到抖店\\|抖店助手\\|没有读取到' /app /usr /var /www /frontend /dist /static 2>/dev/null | head -40" || true
echo '=== commander mounts ==='
docker inspect commander-server-t260220 --format '{{range .Mounts}}{{.Source}}->{{.Destination}};{{end}}'
echo '=== list /data/commander ==='
ls -la /data/commander 2>/dev/null | head -40
find /data/commander /opt -maxdepth 3 -iname '*auto*upload*' 2>/dev/null | head -20
find /opt/1panel/www/sites/www.yoto.work -maxdepth 3 -type d 2>/dev/null | head -40
`
  c.exec(cmd, (e, stream) => {
    let o = ''
    stream.on('data', (d) => (o += d))
    stream.stderr.on('data', (d) => (o += d))
    stream.on('close', () => {
      console.log(o)
      c.end()
    })
  })
}).connect({
  host: process.env.CROSSHUB_SSH_HOST || '124.223.27.98',
  username: 'root',
  password: process.env.CROSSHUB_SSH_PASSWORD || 'Hyh3202276686@@@',
})
