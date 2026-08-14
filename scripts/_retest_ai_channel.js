const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
set +e
KEY=$(grep -oE 'Bearer sk-[^"]+' /opt/1panel/www/sites/www.yoto.work/proxy/hyhacct-image.conf | head -1 | sed 's/Bearer //')
echo "=== 1) direct hyhacct generations ==="
START=$(date +%s)
CODE=$(curl -sS -o /tmp/ai_d.json -w "%{http_code}" --max-time 120 -X POST https://api.hyhacct.com/v1/images/generations \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-image-2-max","prompt":"a simple orange on white background product photo","n":1,"size":"1024x1024","response_format":"url"}')
END=$(date +%s)
echo "http=$CODE sec=$((END-START)) bytes=$(wc -c </tmp/ai_d.json 2>/dev/null || echo 0)"
python3 - <<'PY'
import json,os
p='/tmp/ai_d.json'
if not os.path.exists(p) or os.path.getsize(p)==0:
  print('result=EMPTY'); raise SystemExit
d=json.load(open(p))
err=d.get('error')
if err:
  print('result=FAIL', (err.get('message') if isinstance(err,dict) else err)[:240])
else:
  data=d.get('data') or []
  url=(data[0].get('url') if data else '') or ''
  print('result=OK has_url=', bool(url), 'url_prefix=', url[:90])
PY

echo "=== 2) via local nginx api-proxy (127.0.0.1 Host) ==="
# hit local openresty if possible; else public
START=$(date +%s)
CODE=$(curl -sS -o /tmp/ai_p.json -w "%{http_code}" --max-time 120 -X POST https://www.yoto.work/api-proxy/images/generations \
  -H "Content-Type: application/json" \
  -H "Host: www.yoto.work" \
  -d '{"model":"gpt-image-2-max","prompt":"a simple green cup product photo","n":1,"size":"1024x1024","response_format":"url"}')
END=$(date +%s)
echo "http=$CODE sec=$((END-START)) bytes=$(wc -c </tmp/ai_p.json 2>/dev/null || echo 0)"
python3 - <<'PY'
import json,os
p='/tmp/ai_p.json'
if not os.path.exists(p) or os.path.getsize(p)==0:
  print('result=EMPTY'); raise SystemExit
d=json.load(open(p))
err=d.get('error')
if err:
  print('result=FAIL', (err.get('message') if isinstance(err,dict) else err)[:240])
else:
  data=d.get('data') or []
  url=(data[0].get('url') if data else '') or ''
  print('result=OK has_url=', bool(url), 'url_prefix=', url[:90])
PY

echo "=== 3) recent access codes (last hour window by clock) ==="
NOW_H=$(date +%H)
grep "13/Aug/2026" /opt/1panel/www/sites/www.yoto.work/log/access.log | grep "api-proxy/images" | awk -v h="$NOW_H" '
  match($4,/\\[13\\/Aug\\/2026:([0-9]{2})/,m){ hh=m[1]+0; if(hh>=15) print $9 }
' | sort | uniq -c | sort -nr | head
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
