const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  // Use stdbuf and shorter parallel-safe single probe first
  const cmd = `python3 - <<'PY'
import json, subprocess, time, os, re
conf='/opt/1panel/www/sites/www.yoto.work/proxy/hyhacct-image.conf'
text=open(conf,encoding='utf-8',errors='ignore').read()
m=re.search(r'Bearer (sk-[^"\\s]+)', text)
key=m.group(1) if m else ''
print('key_set=', bool(key))

def post(url, headers, body, timeout=100):
    t0=time.time()
    try:
        r=subprocess.run([
            'curl','-sS','-o','/tmp/ai_out.json','-w','%{http_code}',
            '--max-time',str(timeout),'-X','POST',url,
            *sum([['-H',f'{k}: {v}'] for k,v in headers.items()],[]),
            '-d',body
        ], capture_output=True, text=True, timeout=timeout+10)
        sec=round(time.time()-t0,1)
        code=r.stdout.strip() or '000'
        err=(r.stderr or '').strip()[-200:]
        raw=open('/tmp/ai_out.json','rb').read() if os.path.exists('/tmp/ai_out.json') else b''
        msg=''
        ok=False
        try:
            d=json.loads(raw.decode('utf-8','ignore') or '{}')
            e=d.get('error')
            if e:
                msg=(e.get('message') if isinstance(e,dict) else str(e))[:200]
            else:
                data=d.get('data') or []
                ok=bool(data and (data[0].get('url') or data[0].get('b64_json')))
                msg='url' if (data and data[0].get('url')) else ('b64' if (data and data[0].get('b64_json')) else 'no_data')
        except Exception as ex:
            msg=f'parse_err {ex} raw={raw[:120]!r}'
        return code, sec, len(raw), ok, msg, err
    except Exception as ex:
        return '000', round(time.time()-t0,1), 0, False, str(ex), ''

body='{"model":"gpt-image-2-max","prompt":"simple orange fruit white bg","n":1,"size":"1024x1024","response_format":"url"}'
print('=== direct hyhacct ===', flush=True)
code,sec,n,ok,msg,err=post('https://api.hyhacct.com/v1/images/generations', {
    'Authorization': f'Bearer {key}',
    'Content-Type':'application/json',
}, body)
print(f'http={code} sec={sec} bytes={n} ok={ok} detail={msg}', flush=True)
if err: print('curl_err=', err, flush=True)

print('=== via www.yoto.work/api-proxy ===', flush=True)
code,sec,n,ok,msg,err=post('https://www.yoto.work/api-proxy/images/generations', {
    'Content-Type':'application/json',
}, body)
print(f'http={code} sec={sec} bytes={n} ok={ok} detail={msg}', flush=True)
if err: print('curl_err=', err, flush=True)

print('=== access log since 15:00 ===', flush=True)
import collections
cnt=collections.Counter()
with open('/opt/1panel/www/sites/www.yoto.work/log/access.log','r',errors='ignore') as f:
    for line in f:
        if 'api-proxy/images' not in line: continue
        if '13/Aug/2026:1' not in line and '13/Aug/2026:16' not in line: continue
        # afternoon 15-16
        if not any(x in line for x in [':15:',':16:']): continue
        parts=line.split()
        if len(parts)>8: cnt[parts[8]]+=1
print(dict(cnt), flush=True)
PY`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>{process.stdout.write(d); o+=d;});
    stream.stderr.on('data',d=>{process.stderr.write(d); o+=d;});
    stream.on('close',()=>{c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
