const { Client } = require('ssh2')
const c = new Client()
c.on('ready', () => {
  const cmd = `
echo '=== config hyhacct ==='
python3 -c "import yaml,re; h=yaml.safe_load(open('/data/commander/config/config.yaml'))['hyhacct']; print({k:('***' if 'key' in k else v) for k,v in h.items()})"

echo '=== curl models ==='
KEY=$(python3 -c "import yaml; print(yaml.safe_load(open('/data/commander/config/config.yaml'))['hyhacct']['api_key'])")
curl -sS --max-time 30 -w '\\nHTTP=%{http_code}\\n' -H "Authorization: Bearer $KEY" https://api.hyhacct.com/v1/models | head -c 800
echo
echo '=== curl generations gpt-image-2-max low ==='
curl -sS --max-time 150 -w '\\nHTTP=%{http_code}\\n' -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"gpt-image-2-max","prompt":"simple red apple on white","n":1,"size":"1024x1024","quality":"low"}' \
  https://api.hyhacct.com/v1/images/generations | head -c 600
echo
echo '=== curl generations gpt-image-2 ==='
curl -sS --max-time 90 -w '\\nHTTP=%{http_code}\\n' -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"gpt-image-2","prompt":"simple red apple on white","n":1,"size":"1024x1024"}' \
  https://api.hyhacct.com/v1/images/generations | head -c 600
echo
echo '=== curl chat ==='
curl -sS --max-time 40 -w '\\nHTTP=%{http_code}\\n' -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"gpt-5.5","messages":[{"role":"user","content":"ping"}],"max_tokens":8}' \
  https://api.hyhacct.com/v1/chat/completions | head -c 400
echo
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
