const { Client } = require('ssh2')
const c = new Client()
c.on('ready', () => {
  const cmd = `
echo '=== commander status ==='
docker inspect commander-server-t260220 --format 'Status={{.State.Status}} OOM={{.State.OOMKilled}} Exit={{.State.ExitCode}} Mem={{.HostConfig.Memory}} RestartCount={{.RestartCount}} Started={{.State.StartedAt}}' 2>/dev/null || docker ps -a --filter name=commander --format '{{.Names}} {{.Status}}'
echo '=== mem ==='
docker stats --no-stream --format '{{.Name}} {{.MemUsage}} {{.MemPerc}}' commander-server-t260220 2>/dev/null || true
echo '=== task_list local probe ==='
USER=$(docker exec crosshub-java sh -c 'printenv CROSSHUB_COMMANDER_USERNAME')
PASS=$(docker exec crosshub-java sh -c 'printenv CROSSHUB_COMMANDER_PASSWORD' | tr -d '\\r')
BASE=$(docker exec crosshub-java sh -c 'printenv CROSSHUB_COMMANDER_BASE_URL' || echo 'http://172.17.0.1:34206')
LOGIN=$(curl -sS --max-time 15 -X POST "$BASE/api/v1/user/login" -H 'Content-Type: application/json' -d "{\"username\":\"$USER\",\"password\":\"$PASS\"}")
TOKEN=$(echo "$LOGIN" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("data",{}).get("token") or d.get("token") or "")' 2>/dev/null)
echo "login_ok=$([ -n \"$TOKEN\" ] && echo yes || echo no)"
if [ -n "$TOKEN" ]; then
  for i in 1 2 3; do
    CODE=$(curl -sS -o /tmp/tl.json -w '%{http_code}' --max-time 30 -X POST "$BASE/api/v1/agent/task_list" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"agent_id":"","platform":"temu","page":1,"page_size":5,"list_scope":"active"}')
    echo "probe$i http=$CODE"
  done
  echo '=== recent failed tasks (msg sample) ==='
  python3 - <<'PY'
import json
try:
  d=json.load(open('/tmp/tl.json'))
  rows=(d.get('data') or {}).get('list') or (d.get('data') or {}).get('rows') or d.get('data') or []
  if isinstance(rows, dict):
    rows=rows.get('list') or rows.get('rows') or []
  print('rows', len(rows) if isinstance(rows, list) else type(rows))
  if isinstance(rows, list):
    for r in rows[:8]:
      st=r.get('status') or r.get('task_status') or ''
      msg=(r.get('msg') or r.get('message') or r.get('error') or r.get('fail_reason') or '')[:180]
      name=(r.get('name') or r.get('task_name') or r.get('product_name') or '')[:60]
      print(f"status={st} name={name} msg={msg}")
except Exception as e:
  print('parse_err', e)
  print(open('/tmp/tl.json').read()[:500])
PY
fi
echo '=== recent commander logs image/oom ==='
docker logs commander-server-t260220 --since 6h 2>&1 | grep -iE 'oom|killed|grsai|hyhacct|image|生图|generate|gpt-image|failed to download|out of memory' | tail -40 || true
echo '=== java proxy errors ==='
docker logs crosshub-java --since 6h 2>&1 | grep -iE 'Commander|BAD_GATEWAY|502|代理失败|task_list' | tail -30 || true
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
