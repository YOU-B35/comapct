/**
 * Diagnose CrossHub /api-proxy → hyhacct path (redacts secrets).
 * CROSSHUB_SSH_PASSWORD=... node scripts/_diag_ai_image_proxy_now.js
 */
const { Client } = require('ssh2')

const host = process.env.CROSSHUB_SSH_HOST || '124.223.27.98'
const password = process.env.CROSSHUB_SSH_PASSWORD
if (!password) {
  console.error('CROSSHUB_SSH_PASSWORD required')
  process.exit(1)
}

const cmd = `
set +e
echo '=== proxy conf files ==='
ls -la /opt/1panel/www/sites/www.yoto.work/proxy/ 2>/dev/null | grep -iE 'hy|gpt|image|proxy|api' || true
echo '=== grep api-proxy locations ==='
grep -RIn --include='*.conf' 'api-proxy\\|hyhacct\\|images/generations' /opt/1panel/www/sites/www.yoto.work/proxy/ 2>/dev/null | sed -E 's/(Bearer sk-)[A-Za-z0-9_-]+/\\1***REDACTED***/g' | head -80
echo '=== openresty error (hyhacct/ssl) ==='
ERRLOG=\$(docker exec 1Panel-openresty-UN3Y sh -c 'ls /www/sites/www.yoto.work/log/error.log 2>/dev/null; ls /var/log/nginx/error.log 2>/dev/null' | head -1)
echo "errlog=\$ERRLOG"
if [ -n "\$ERRLOG" ]; then
  docker exec 1Panel-openresty-UN3Y sh -c "tail -n 200 '\$ERRLOG'" 2>/dev/null | grep -iE 'hyhacct|api-proxy|upstream|SSL|ssl' | tail -40
fi
echo '=== local curl retry with --http1.1 / insecure ==='
curl -sS --http1.1 --max-time 25 -o /tmp/hy_models_h11.json -w 'h11_http=%{http_code} time=%{time_total}\\n' https://api.hyhacct.com/v1/models || true
curl -sk --max-time 25 -o /tmp/hy_models_k.json -w 'insecure_http=%{http_code} time=%{time_total}\\n' https://api.hyhacct.com/v1/models || true
echo '=== resolve + ping route ==='
ip route get 1.1.1.1 2>/dev/null | head -1 || true
getent ahosts api.hyhacct.com | head -5 || true
`

const c = new Client()
c.on('ready', () => {
  c.exec(cmd, (err, stream) => {
    if (err) throw err
    let out = ''
    stream.on('data', (d) => { out += d.toString() })
    stream.stderr.on('data', (d) => { out += d.toString() })
    stream.on('close', () => {
      console.log(out)
      c.end()
    })
  })
})
c.on('error', (e) => {
  console.error(e)
  process.exit(1)
})
c.connect({
  host,
  port: 22,
  username: process.env.CROSSHUB_SSH_USER || 'root',
  password,
  readyTimeout: 60000,
})
