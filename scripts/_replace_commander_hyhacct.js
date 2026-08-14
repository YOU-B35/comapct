const { Client } = require('ssh2')
const fs = require('fs')

const DOC = String.raw`c:\Users\Administrator\Desktop\新建文本文档 (2).txt`
const text = fs.readFileSync(DOC, 'utf8')
let base = ''
let key = ''
for (const line of text.split(/\r?\n/)) {
  const t = line.trim()
  if (/^curl\s*=/i.test(t)) base = t.split('=').slice(1).join('=').trim()
  if (/^api\s*key\s*=/i.test(t)) key = t.split('=').slice(1).join('=').trim()
}
if (!base || !key) {
  console.error('parse failed', { base, keyLen: key.length })
  process.exit(1)
}
// Commander appends /v1/... itself; strip trailing /v1
let url = base.replace(/\/+$/, '')
if (/\/v1$/i.test(url)) url = url.replace(/\/v1$/i, '')
console.log('parsed url=', url, 'key_len=', key.length, 'prefix=', key.slice(0, 6))

const c = new Client()
c.on('ready', () => {
  // pass via env in remote python to avoid shell escaping issues
  const b64url = Buffer.from(url).toString('base64')
  const b64key = Buffer.from(key).toString('base64')
  const cmd = `
set -e
CFG=/data/commander/config/config.yaml
cp -a "$CFG" "$CFG.bak.$(date +%Y%m%d%H%M%S)"
echo '${b64url}' | base64 -d > /tmp/_hy_url.txt
echo '${b64key}' | base64 -d > /tmp/_hy_key.txt
python3 <<'PY'
import re, pathlib
cfg_path = pathlib.Path('/data/commander/config/config.yaml')
text = cfg_path.read_text(encoding='utf-8')
url = pathlib.Path('/tmp/_hy_url.txt').read_text().strip()
key = pathlib.Path('/tmp/_hy_key.txt').read_text().strip()

lines = text.splitlines(True)
out = []
in_hy = False
seen = set()
for line in lines:
    if re.match(r'^hyhacct:\\s*$', line):
        in_hy = True
        out.append(line)
        continue
    if in_hy and re.match(r'^[a-zA-Z]', line):
        in_hy = False
    if in_hy:
        m = re.match(r'^(\\s*)(url|api_key|api_key_chat)\\s*:\\s*.*$', line)
        if m:
            indent, field = m.group(1), m.group(2)
            if field == 'url':
                out.append(f'{indent}url: {url}\\n')
            else:
                out.append(f'{indent}{field}: {key}\\n')
            seen.add(field)
            continue
    out.append(line)

if 'url' not in seen or 'api_key' not in seen:
    raise SystemExit(f'missing fields in hyhacct: {seen}')

new = ''.join(out)
cfg_path.write_text(new, encoding='utf-8')
print('updated fields:', sorted(seen))
for line in new.splitlines():
    if line.startswith('hyhacct:') or (line.startswith('  ') and any(line.strip().startswith(p) for p in ('url:', 'api_key', 'model_', 'chat_'))):
        if 'api_key' in line:
            print(re.sub(r'(api_key(?:_chat)?)\\s*:\\s*\\S+', r'\\1: ***', line))
        else:
            print(line)
pathlib.Path('/tmp/_hy_url.txt').unlink(missing_ok=True)
pathlib.Path('/tmp/_hy_key.txt').unlink(missing_ok=True)
PY

echo '=== restart commander to reload config ==='
docker restart commander-server-t260220 >/dev/null
sleep 5
docker inspect commander-server-t260220 --format 'Status={{.State.Status}} Started={{.State.StartedAt}}'

echo '=== probe new image api ==='
python3 - <<'PY'
import json, urllib.request, ssl, yaml
cfg=yaml.safe_load(open('/data/commander/config/config.yaml'))
h=cfg['hyhacct']
url=h['url'].rstrip('/')
key=h.get('api_key') or h.get('api_key_chat')
model=h.get('model_images') or 'gpt-image-2'
print('url=', url, 'model=', model, 'key_prefix=', key[:6], 'key_len=', len(key))
ctx=ssl.create_default_context()

def post(path, body, timeout=90):
  r=urllib.request.Request(url+path, data=json.dumps(body).encode(), method='POST')
  r.add_header('Authorization','Bearer '+key)
  r.add_header('Content-Type','application/json')
  try:
    with urllib.request.urlopen(r, context=ctx, timeout=timeout) as resp:
      raw=resp.read()[:500]
      print(path, 'HTTP', resp.status, raw[:300])
  except Exception as e:
    body=getattr(getattr(e,'fp',None),'read',lambda:b'')()
    print(path, 'ERR', getattr(e,'code',None), str(e)[:180], (body or b'')[:300])

post('/v1/images/generations', {
  'model': model,
  'prompt': 'simple red apple on white background product photo',
  'n': 1,
  'size': '1024x1024',
  'quality': 'low',
}, timeout=120)
# also try max model if base fails
post('/v1/images/generations', {
  'model': 'gpt-image-2-max',
  'prompt': 'simple red apple on white background product photo',
  'n': 1,
  'size': '1024x1024',
  'quality': 'low',
}, timeout=120)
post('/v1/chat/completions', {
  'model': h.get('model_chat') or 'gpt-5.5',
  'messages':[{'role':'user','content':'ping'}],
  'max_tokens': 8,
}, timeout=40)
PY
`
  c.exec(cmd, (err, stream) => {
    if (err) throw err
    let out = ''
    stream.on('data', (d) => { out += d.toString() })
    stream.stderr.on('data', (d) => { out += d.toString() })
    stream.on('close', (code) => {
      console.log(out)
      process.exit(code || 0)
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
