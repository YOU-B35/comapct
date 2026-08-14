const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `python3 - <<'PY'
import json,subprocess,time,os,collections
out='/tmp/ai_local_https.json'
try: os.remove(out)
except FileNotFoundError: pass
body='{"model":"gpt-image-2-max","prompt":"simple red apple","n":1,"size":"1024x1024","response_format":"url"}'
t0=time.time()
r=subprocess.run([
  'curl','-sS','-k','-o',out,'-w','%{http_code}','--max-time','110','-X','POST',
  'https://127.0.0.1/api-proxy/images/generations',
  '-H','Host: www.yoto.work','-H','Content-Type: application/json','-d',body
], capture_output=True, text=True)
sec=round(time.time()-t0,1)
code=(r.stdout or '').strip() or '000'
raw=open(out,'rb').read() if os.path.exists(out) else b''
print('local_https_http=', code, 'sec=', sec, 'bytes=', len(raw), flush=True)
if (r.stderr or '').strip():
  print('err=', r.stderr.strip()[-220], flush=True)
if raw:
  try:
    d=json.loads(raw.decode('utf-8','ignore'))
  except Exception as e:
    print('raw_head=', raw[:160], flush=True); raise
  err=d.get('error')
  if err:
    print('FAIL', (err.get('message') if isinstance(err,dict) else err)[:240], flush=True)
  else:
    data=d.get('data') or []
    print('OK has_url=', bool(data and data[0].get('url')), flush=True)
else:
  print('EMPTY', flush=True)

cnt=collections.Counter()
with open('/opt/1panel/www/sites/www.yoto.work/log/access.log','r',errors='ignore') as f:
  for line in f:
    if 'api-proxy/images' not in line: continue
    if '13/Aug/2026:15' not in line and '13/Aug/2026:16' not in line: continue
    parts=line.split()
    if len(parts)>8: cnt[parts[8]] += 1
print('access_15_16=', dict(cnt), flush=True)
print('--- last 10 ---', flush=True)
os.system("grep 'api-proxy/images' /opt/1panel/www/sites/www.yoto.work/log/access.log | tail -10 | awk '{print $4,$7,$9,$10}'")
PY`;
  c.exec(cmd,(e,stream)=>{
    stream.on('data',d=>process.stdout.write(d));
    stream.stderr.on('data',d=>process.stderr.write(d));
    stream.on('close',()=>c.end());
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
