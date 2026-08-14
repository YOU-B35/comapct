const { Client } = require('ssh2')
const c = new Client()
c.on('ready', () => {
  const cmd = `
set +e
echo '=== 1. config ==='
python3 -c "import yaml; h=yaml.safe_load(open('/data/commander/config/config.yaml'))['hyhacct']; print('url=',h.get('url')); print('model=',h.get('model_images')); print('key_prefix=',(h.get('api_key') or '')[:8], 'len=',len(h.get('api_key') or ''))"

KEY=$(python3 -c "import yaml; print(yaml.safe_load(open('/data/commander/config/config.yaml'))['hyhacct']['api_key'])")
URL=$(python3 -c "import yaml; print(yaml.safe_load(open('/data/commander/config/config.yaml'))['hyhacct']['url'].rstrip('/'))")

echo '=== 2. TCP/SSL to api.hyhacct.com ==='
timeout 8 bash -c 'echo >/dev/tcp/api.hyhacct.com/443' && echo tcp_ok || echo tcp_fail
curl -sS --max-time 20 -o /tmp/hy_models.json -w 'models_http=%{http_code} time=%{time_total}\\n' -H "Authorization: Bearer $KEY" "$URL/v1/models"
head -c 400 /tmp/hy_models.json 2>/dev/null; echo

echo '=== 3. generations gpt-image-2-max quality=low (120s) ==='
curl -sS --max-time 120 -o /tmp/hy_gen.json -w 'gen_http=%{http_code} time=%{time_total}\\n' \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"gpt-image-2-max","prompt":"simple red apple product photo on white background","n":1,"size":"1024x1024","quality":"low"}' \
  "$URL/v1/images/generations"
python3 - <<'PY'
import json
try:
  d=json.load(open('/tmp/hy_gen.json'))
  if 'error' in d:
    print('error=', d['error'])
  elif 'data' in d:
    item=(d.get('data') or [{}])[0]
    url=item.get('url') or ''
    b64=item.get('b64_json') or ''
    print('ok images=', len(d.get('data') or []), 'has_url=', bool(url), 'url_prefix=', url[:80], 'b64_len=', len(b64))
  else:
    print('body=', open('/tmp/hy_gen.json').read()[:500])
except Exception as e:
  print('parse_err', e, open('/tmp/hy_gen.json').read()[:400])
PY

echo '=== 4. generations gpt-image-2 (60s) ==='
curl -sS --max-time 60 -o /tmp/hy_gen2.json -w 'gen2_http=%{http_code} time=%{time_total}\\n' \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"gpt-image-2","prompt":"simple red apple","n":1,"size":"1024x1024"}' \
  "$URL/v1/images/generations"
head -c 350 /tmp/hy_gen2.json; echo

echo '=== 5. chat ping ==='
curl -sS --max-time 30 -o /tmp/hy_chat.json -w 'chat_http=%{http_code} time=%{time_total}\\n' \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"gpt-5.5","messages":[{"role":"user","content":"ping"}],"max_tokens":8}' \
  "$URL/v1/chat/completions"
head -c 250 /tmp/hy_chat.json; echo

echo '=== 6. site api-proxy ==='
curl -sS --max-time 90 -o /tmp/proxy_gen.json -w 'proxy_http=%{http_code} time=%{time_total}\\n' \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"gpt-image-2-max","prompt":"simple red apple","n":1,"size":"1024x1024","quality":"low"}' \
  https://www.yoto.work/api-proxy/images/generations
head -c 350 /tmp/proxy_gen.json; echo
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
