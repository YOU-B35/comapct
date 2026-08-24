const { Client } = require('ssh2');
const fs = require('fs');

const HOST = '124.223.27.98';
const KEY = 'C:/Users/Administrator/.ssh/lhkp-o3wazsuv';

const cmd = `
echo "=== now ==="
date '+%Y-%m-%d %H:%M:%S'
echo
echo "=== automedia access log last 45min non-200 (errors) ==="
awk -v d="$(date -d '45 minutes ago' '+%d/%b/%Y:%H:%M')" '$0 >= "[" d' /opt/1panel/www/sites/autoMedia.yoto.work/log/access.log 2>/dev/null | grep -vE '" (200|304|302) ' | tail -60
echo
echo "=== automedia docker logs errors (30m) ==="
docker logs automedia-social-auto-upload --since 30m 2>&1 | grep -aiE "error|fail|exception|traceback|500|502|403|401|失败|超时" | grep -avE "login-agent/(heartbeat|poll)" | tail -60
echo
echo "=== crosshub java logs errors (30m) ==="
docker logs crosshub-java --since 30m 2>&1 | grep -aiE "error|exception|warn|sau|exchange|401|403|500" | tail -50
echo
echo "=== www.yoto.work access log sau/token last 45min ==="
awk -v d="$(date -d '45 minutes ago' '+%d/%b/%Y:%H:%M')" '$0 >= "[" d' /opt/1panel/www/sites/www.yoto.work/log/access.log 2>/dev/null | grep -E "sau/token|getAccounts|auth/me" | tail -40
`;

const c = new Client();
c.on('ready', () => {
  c.exec(cmd, (err, stream) => {
    if (err) { console.error(err); process.exit(1); }
    let out = '';
    stream.on('data', (d) => (out += d.toString()));
    stream.stderr.on('data', (d) => (out += d.toString()));
    stream.on('close', () => { console.log(out); c.end(); });
  });
});
c.on('error', (e) => { console.error('SSH_ERR', e.message); process.exit(1); });
c.connect({ host: HOST, port: 22, username: 'root', privateKey: fs.readFileSync(KEY), readyTimeout: 30000 });
