const { Client } = require('ssh2')
const c = new Client()
c.on('ready', () => {
  const cmd = `
echo '=== dns ==='
getent hosts api.hyhacct.com || nslookup api.hyhacct.com || true
echo '=== openssl ==='
timeout 15 openssl s_client -connect api.hyhacct.com:443 -servername api.hyhacct.com </dev/null 2>&1 | head -30
echo '=== curl -v short ==='
curl -v --max-time 20 https://api.hyhacct.com/v1/models 2>&1 | tail -40
echo '=== from docker host network ==='
docker run --rm --network host curlimages/curl:8.5.0 -sS --max-time 25 -w 'HTTP=%{http_code}\\n' https://api.hyhacct.com/v1/models | head -c 300 || true
echo '=== compare grsai ==='
curl -sS --max-time 15 -o /dev/null -w 'grsai=%{http_code}\\n' https://grsaiapi.com/ || true
`
  c.exec(cmd, (err, stream) => {
    if (err) throw err
    let out = ''
    stream.on('data', (d) => { out += d.toString() })
    stream.stderr.on('data', (d) => { out += d.toString() })
    stream.on('close', () => { console.log(out); c.end() })
  })
})
c.on('error', (e) => { console.error(e); process.exit(1) })
c.connect({
  host: process.env.CROSSHUB_SSH_HOST || '124.223.27.98',
  port: 22,
  username: 'root',
  password: process.env.CROSSHUB_SSH_PASSWORD,
  readyTimeout: 20000,
})
