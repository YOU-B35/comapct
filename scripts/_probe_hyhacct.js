const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  // Get auth header from conf without printing full key in our analysis output later
  const cmd = `
KEY=$(grep -oE 'Bearer sk-[^"]+' /opt/1panel/www/sites/www.yoto.work/proxy/hyhacct-image.conf | head -1 | sed 's/Bearer //')
# Capture a tiny generations call to see if API alive, then note: we cannot easily redo edits without image.
# Instead dump any cached response from access if unavailable: use curl against hyhacct with invalid tiny edit to see error shape
# Prefer: check if 11:56 response body pattern by reproducing with empty image? skip.
echo "=== probe generations status (no image dump) ==="
CODE=$(curl -s -o /tmp/ai_probe.json -w "%{http_code}" -X POST https://api.hyhacct.com/v1/images/generations \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-image-2-max","prompt":"red apple on white","n":1,"size":"1024x1024","response_format":"url"}' --max-time 120)
echo "generations_http=$CODE"
python3 - <<'PY'
import json
p='/tmp/ai_probe.json'
try:
  d=json.load(open(p))
except Exception as e:
  print('body_raw', open(p,'rb').read()[:300]); raise SystemExit
err=d.get('error') if isinstance(d,dict) else None
if err:
  print('error_message=', (err.get('message') if isinstance(err,dict) else err)[:300])
else:
  data=d.get('data') if isinstance(d,dict) else None
  if isinstance(data,list) and data:
    u=data[0].get('url') or ('b64_json' in data[0] and 'b64_len='+str(len(data[0].get('b64_json') or '')))
    print('ok_url_or_b64=', str(u)[:120])
  else:
    print('keys=', list(d.keys())[:20] if isinstance(d,dict) else type(d))
print('body_len=', len(open(p,'rb').read()))
PY
# Also check what HTTP status hyhacct returns for a fake download-error message search in docs - skip
echo "=== nginx status for matching 502 body size 156 ==="
# Simulate: ask hyhacct edits with no image to see error text length
CODE2=$(curl -s -o /tmp/ai_edit.json -w "%{http_code}" -X POST https://api.hyhacct.com/v1/images/edits \
  -H "Authorization: Bearer $KEY" \
  -F "model=gpt-image-2-max" -F "prompt=make brighter" -F "n=1" -F "size=1024x1024" --max-time 60)
echo "edits_no_image_http=$CODE2 body_len=$(wc -c </tmp/ai_edit.json)"
python3 - <<'PY'
import json
d=json.load(open('/tmp/ai_edit.json'))
err=d.get('error') if isinstance(d,dict) else None
print('edit_err=', (err.get('message') if isinstance(err,dict) else err))
PY
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
