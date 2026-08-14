const { Client } = require('ssh2')
const c = new Client()
c.on('ready', () => {
  const cmd = `
python3 <<'PY'
import json, urllib.request, ssl, yaml, re, time
cfg=yaml.safe_load(open('/data/commander/config/config.yaml'))
h=cfg.get('hyhacct') or {}
url=(h.get('url') or '').rstrip('/')
key=h.get('api_key') or h.get('api_key_chat') or ''
model=h.get('model_images') or 'gpt-image-2'
print('url=', url)
print('model=', model)
print('key_len=', len(key), 'prefix=', key[:6] if key else '')

ctx=ssl.create_default_context()

def req(path, body=None, method='GET', timeout=40):
  data=None if body is None else json.dumps(body).encode()
  r=urllib.request.Request(url+path, data=data, method=method)
  r.add_header('Authorization','Bearer '+key)
  r.add_header('Content-Type','application/json')
  try:
    with urllib.request.urlopen(r, context=ctx, timeout=timeout) as resp:
      raw=resp.read()[:800]
      print(path, 'HTTP', resp.status, raw[:400])
      return resp.status, raw
  except Exception as e:
    body=getattr(getattr(e,'fp',None),'read',lambda:b'')()
    code=getattr(e,'code',None)
    print(path, 'ERR', code, str(e)[:200], (body or b'')[:400])
    return code, body

# common endpoints
req('/v1/models')
req('/api/generate', {
  'model': model,
  'prompt': 'simple red apple product photo on white',
  'n': 1,
  'size': '1024x1024',
}, 'POST', timeout=60)
req('/v1/images/generations', {
  'model': model,
  'prompt': 'simple red apple product photo on white',
  'n': 1,
  'size': '1024x1024',
}, 'POST', timeout=60)
req('/v1/chat/completions', {
  'model': h.get('model_chat') or 'gpt-5.5',
  'messages':[{'role':'user','content':'ping'}],
  'max_tokens': 8,
}, 'POST', timeout=40)
PY

echo '=== deeper produce image errors ==='
docker logs commander-server-t260220 --since 6h 2>&1 | grep -iE '轮播|produce|generate|Hyhacct|grsai|api/generate|images/gener|chat/completions|原型图|失败' | grep -v GIN-debug | tail -60
`
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
