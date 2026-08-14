const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
CODE=$(curl -s -o /tmp/ai_proxy3.json -w "%{http_code}" --max-time 120 -X POST https://www.yoto.work/api-proxy/images/generations \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-image-2-max","prompt":"simple blue cup on table","n":1,"size":"1024x1024","response_format":"url"}')
echo "proxy_http=$CODE body_len=$(wc -c </tmp/ai_proxy3.json 2>/dev/null || echo 0)"
python3 - <<'PY'
import json,os
p='/tmp/ai_proxy3.json'
if not os.path.exists(p) or os.path.getsize(p)==0:
  print('empty'); raise SystemExit
d=json.load(open(p))
err=d.get('error') if isinstance(d,dict) else None
if err:
  print('error=', (err.get('message') if isinstance(err,dict) else err)[:300])
else:
  data=d.get('data') or []
  print('ok=', bool(data), 'url=', bool(data and data[0].get('url')))
PY
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
