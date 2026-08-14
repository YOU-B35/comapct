const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
python3 - <<'PY'
import json,os,datetime
base='/opt/autoMedia-social-auto-upload/deploy/data/cookiesFile'
pairs=[('YOTO欧鲤钓','c2fe38fa-8af1-11f1-a628-6ea8f5bd029d.json'),('渔具厂的歌神','9c93c248-8bf0-11f1-8e90-4e8c12a8480d.json')]
need=['sessionid','sessionid_ss','sid_tt','uid_tt','passport_csrf_token','odin_tt','ttwid']
for name,fn in pairs:
  data=json.load(open(os.path.join(base,fn),encoding='utf-8'))
  cookies=data.get('cookies') if isinstance(data,dict) else data
  print('====', name, '====')
  print('cookie_count', len(cookies))
  by={c.get('name'):c for c in cookies if isinstance(c,dict)}
  for k in need:
    c=by.get(k)
    if not c:
      print(k, 'MISSING'); continue
    exp=c.get('expires') or c.get('expirationDate')
    print(k, 'YES', 'domain=', c.get('domain'), 'expires=', exp)
  # print domains summary
  domains=sorted({c.get('domain') for c in cookies if isinstance(c,dict)})
  print('domains', domains[:12])

import urllib.request
# job status
for port in (18302,5409):
  try:
    url=f'http://127.0.0.1:{port}/publish/jobs/c9906099-77d3-46a5-837e-3df59d08f13a'
    with urllib.request.urlopen(url, timeout=5) as r:
      body=r.read().decode('utf-8','ignore')
      print('JOB', port, r.status, body[:1500])
  except Exception as e:
    print('JOB', port, 'ERR', e)

# list recent jobs if endpoint exists
for path in ['/publish/jobs','/api/publish/jobs','/getFileName']:
  try:
    with urllib.request.urlopen(f'http://127.0.0.1:18302{path}', timeout=3) as r:
      print('PATH', path, r.status, r.read()[:200])
  except Exception as e:
    print('PATH', path, type(e).__name__, e)
PY

echo "=== agent bind vs heartbeats ==="
docker logs automedia-social-auto-upload --since 3h 2>&1 | grep -E "POST /publish|account|歌神|欧鲤|job_id|failed|success|timeout|agent" | grep -v download | grep -v heartbeat | tail -80

echo "=== publish POST today ==="
docker logs automedia-social-auto-upload --since 6h 2>&1 | grep -E "POST /publish|POST /upload|POST /file" | tail -40

# extract job statuses by curling while job may still be running - also check redis?
docker exec automedia-social-auto-upload sh -c 'ls /tmp 2>/dev/null; ls /app 2>/dev/null | head; find /app -name "*job*" 2>/dev/null | head -20'
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
