const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
echo "=== recent api-proxy images today ==="
grep "13/Aug/2026:1[3-5]" /opt/1panel/www/sites/www.yoto.work/log/access.log | grep "api-proxy/images" | awk '{print $4,$7,$9,$10}' | tail -40
echo "=== status summary last 2h-ish ==="
grep "13/Aug/2026:1[4-5]" /opt/1panel/www/sites/www.yoto.work/log/access.log | grep "api-proxy/images" | awk '{print $9}' | sort | uniq -c | sort -nr
echo "=== probe hyhacct generations ==="
KEY=$(grep -oE 'Bearer sk-[^"]+' /opt/1panel/www/sites/www.yoto.work/proxy/hyhacct-image.conf | head -1 | sed 's/Bearer //')
CODE=$(curl -s -o /tmp/ai_probe2.json -w "%{http_code}" -X POST https://api.hyhacct.com/v1/images/generations \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-image-2-max","prompt":"simple red apple white background","n":1,"size":"1024x1024","response_format":"url"}' --max-time 90)
echo "generations_http=$CODE body_len=$(wc -c </tmp/ai_probe2.json)"
python3 - <<'PY'
import json
d=json.load(open('/tmp/ai_probe2.json'))
err=d.get('error') if isinstance(d,dict) else None
if err:
  print('error=', (err.get('message') if isinstance(err,dict) else err)[:300])
else:
  data=d.get('data') if isinstance(d,dict) else None
  if isinstance(data,list) and data:
    item=data[0]
    u=item.get('url') or ''
    b=item.get('b64_json') or ''
    print('ok url=', (u[:80]+'...') if u else '', 'b64_len=', len(b))
  else:
    print('keys=', list(d.keys())[:20] if isinstance(d,dict) else type(d))
PY
echo "=== via nginx proxy ==="
CODE2=$(curl -s -o /tmp/ai_proxy2.json -w "%{http_code}" -X POST https://www.yoto.work/api-proxy/images/generations \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-image-2-max","prompt":"simple blue cup","n":1,"size":"1024x1024","response_format":"url"}' --max-time 90)
echo "proxy_http=$CODE2 body_len=$(wc -c </tmp/ai_proxy2.json)"
python3 - <<'PY'
import json
d=json.load(open('/tmp/ai_proxy2.json'))
err=d.get('error') if isinstance(d,dict) else None
if err:
  print('proxy_error=', (err.get('message') if isinstance(err,dict) else err)[:300])
else:
  data=d.get('data') if isinstance(d,dict) else None
  if isinstance(data,list) and data:
    item=data[0]
    print('proxy_ok url=', bool(item.get('url')), 'b64=', bool(item.get('b64_json')))
  else:
    print('proxy_keys=', list(d.keys())[:20] if isinstance(d,dict) else type(d))
PY
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
