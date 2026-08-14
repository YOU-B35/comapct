const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `python3 - <<'PY'
import json,subprocess,time,os
# read key from nginx conf
conf=open('/opt/1panel/www/sites/www.yoto.work/proxy/hyhacct-image.conf').read()
key=None
for line in conf.splitlines():
  if 'Authorization' in line or 'Bearer' in line or 'api-key' in line.lower() or 'x-api' in line.lower():
    print('hdr_line=', line.strip()[:120])
# find upstream and auth from conf
print('--- conf snippet ---')
for line in conf.splitlines():
  if any(k in line for k in ('proxy_pass','Authorization','api','hyhacct','Host','timeout')):
    print(line.rstrip()[:160])

# direct test - extract bearer if present
import re
m=re.search(r'Bearer\\s+([^"\\'\\s;]+)', conf)
auth=m.group(1) if m else None
# also try Authorization header set via proxy_set_header
m2=re.search(r'proxy_set_header\\s+Authorization\\s+"?([^";\\n]+)"?', conf)
if m2: auth_hdr=m2.group(1).strip()
else: auth_hdr=('Bearer '+auth) if auth else None
print('auth_found=', bool(auth_hdr), flush=True)

# find proxy_pass URL
m3=re.search(r'proxy_pass\\s+([^;]+);', conf)
upstream=(m3.group(1).strip() if m3 else '').rstrip('/')
print('upstream=', upstream, flush=True)

if upstream and auth_hdr:
  body='{"model":"gpt-image-2-max","prompt":"simple red apple on white","n":1,"size":"1024x1024","response_format":"url"}'
  url=upstream.rstrip('/')+'/images/generations'
  if not url.startswith('http'):
    # relative - skip
    print('relative upstream skip', flush=True)
  else:
    t0=time.time()
    out='/tmp/ai_direct2.json'
    r=subprocess.run(['curl','-sS','-o',out,'-w','%{http_code}','--max-time','100','-X','POST',url,
      '-H','Content-Type: application/json','-H','Authorization: '+auth_hdr,'-d',body],
      capture_output=True,text=True)
    sec=round(time.time()-t0,1)
    code=(r.stdout or '').strip()
    raw=open(out,'rb').read() if os.path.exists(out) else b''
    print('direct_http=',code,'sec=',sec,'bytes=',len(raw), flush=True)
    if r.stderr: print('stderr=',r.stderr.strip()[-200], flush=True)
    if raw:
      try:
        d=json.loads(raw.decode('utf-8','ignore'))
        err=d.get('error')
        if err:
          print('FAIL', str(err)[:300], flush=True)
        else:
          data=d.get('data') or []
          u=(data[0].get('url') if data else '') or ''
          print('OK url_len=', len(u), 'url_head=', u[:80], flush=True)
      except Exception as e:
        print('parse_err',e,'head',raw[:200], flush=True)
PY`;
  c.exec(cmd,(e,stream)=>{
    stream.on('data',d=>process.stdout.write(d));
    stream.stderr.on('data',d=>process.stderr.write(d));
    stream.on('close',()=>c.end());
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
