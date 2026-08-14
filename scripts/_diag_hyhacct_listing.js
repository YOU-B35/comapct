const { Client } = require('ssh2')
const c = new Client()
c.on('ready', () => {
  const cmd = [
    'echo === config.yaml ===',
    "python3 -c \"import re; t=open('/data/commander/config/config.yaml',encoding='utf-8',errors='ignore').read(); t=re.sub(r'(?i)(api[_-]?key|token|secret|password|authorization)\\s*[:=]\\s*[^\\s\\\"\\']+','\\\\1: ***',t); print(t)\"",
    'echo === recent fail logs ===',
    "docker logs commander-server-t260220 --since 4h 2>&1 | grep -iE 'Hyhacct|轮播图|produce_image|images/generations|grsai|gpt-image|failed to download|余额|quota|taskId=70493240|taskId=f925271c|AI 轮播' | tail -100",
    'echo === probe image api from host ===',
    "python3 -c \"import re,yaml; d=yaml.safe_load(open('/data/commander/config/config.yaml')); print({k:({kk:('***' if 'key' in kk.lower() or 'token' in kk.lower() or 'secret' in kk.lower() or 'pass' in kk.lower() else vv) for kk,vv in (v.items() if isinstance(v,dict) else [])} if isinstance(v,dict) else v) for k,v in (d.items() if isinstance(d,dict) else []) if re.search(r'hyhacct|grsai|image|ai',str(k),re.I) or (isinstance(v,dict) and re.search(r'hyhacct|grsai|gpt-image',str(v),re.I))})\"",
  ].join('\n')
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
c.on('error', (e) => { console.error(e); process.exit(1) })
c.connect({
  host: process.env.CROSSHUB_SSH_HOST || '124.223.27.98',
  port: 22,
  username: 'root',
  password: process.env.CROSSHUB_SSH_PASSWORD,
  readyTimeout: 20000,
})
