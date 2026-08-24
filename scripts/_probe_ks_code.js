const { Client } = require('ssh2');
const fs = require('fs');

const HOST = '124.223.27.98';
const KEY = 'C:/Users/Administrator/.ssh/lhkp-o3wazsuv';

const cmd = `
echo "=== ks_uploader main.py 290-335 (_publish_with_retry) ==="
sed -n '290,335p' /opt/autoMedia-social-auto-upload/app/uploader/ks_uploader/main.py
echo
echo "=== ks_uploader main.py 565,600 (upload loop) ==="
sed -n '565,600p' /opt/autoMedia-social-auto-upload/app/uploader/ks_uploader/main.py
echo
echo "=== douyin.log today publish results (16:00-17:20) ==="
grep -E "2026-08-21 (1[67]):" /opt/autoMedia-social-auto-upload/deploy/data/logs/douyin.log | grep -vE "小人正在努力上传视频" | tail -50
echo
echo "=== 058383b2 account ==="
ls -la /opt/autoMedia-social-auto-upload/deploy/data/cookiesFile/ | grep -i "058383b2" 
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
