const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `python3 - <<'PY'
import json,subprocess,time,os
out='/tmp/ai_proxy_only.json'
try: os.remove(out)
except FileNotFoundError: pass
body='{"model":"gpt-image-2-max","prompt":"simple blue mug white bg","n":1,"size":"1024x1024","response_format":"url"}'
t0=time.time()
r=subprocess.run([
  'curl','-sS','-o',out,'-w','%{http_code}','--max-time','110','-X','POST',
  'https://www.yoto.work/api-proxy/images/generations',
  '-H','Content-Type: application/json','-d',body
], capture_output=True, text=True)
sec=round(time.time()-t0,1)
code=(r.stdout or '').strip() or '000'
raw=open(out,'rb').read() if os.path.exists(out) else b''
print('proxy_http=', code, 'sec=', sec, 'bytes=', len(raw), flush=True)
if r.stderr: print('curl_err=', r.stderr.strip()[-240], flush=True)
if raw:
  d=json.loads(raw.decode('utf-8','ignore'))
  err=d.get('error')
  if err:
    print('FAIL', (err.get('message') if isinstance(err,dict) else err)[:240], flush=True)
  else:
    data=d.get('data') or []
    print('OK has_url=', bool(data and data[0].get('url')), flush=True)
else:
  print('EMPTY body', flush=True)

# also local openresty loopback if port 80/443 inside
t0=time.time()
out2='/tmp/ai_proxy_local.json'
try: os.remove(out2)
except FileNotFoundError: pass
r2=subprocess.run([
  'curl','-sS','-o',out2,'-w','%{http_code}','--max-time','110','-X','POST',
  'http://127.0.0.1/api-proxy/images/generations',
  '-H','Host: www.yoto.work','-H','Content-Type: application/json','-d',body
], capture_output=True, text=True)
sec2=round(time.time()-t0,1)
code2=(r2.stdout or '').strip() or '000'
raw2=open(out2,'rb').read() if os.path.exists(out2) else b''
print('local_http=', code2, 'sec=', sec2, 'bytes=', len(raw2), flush=True)
if r2.stderr: print('local_err=', r2.stderr.strip()[-240], flush=True)
if raw2:
  d=json.loads(raw2.decode('utf-8','ignore'))
  err=d.get('error')
  if err:
    print('local_FAIL', (err.get('message') if isinstance(err,dict) else err)[:240], flush=True)
  else:
    data=d.get('data') or []
    print('local_OK has_url=', bool(data and data[0].get('url')), flush=True)
PY`;
  c.exec(cmd,(e,stream)=>{
    stream.on('data',d=>process.stdout.write(d));
    stream.stderr.on('data',d=>process.stderr.write(d));
    stream.on('close',()=>c.end());
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
