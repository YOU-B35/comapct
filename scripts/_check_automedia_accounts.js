const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
python3 - <<'PY'
import sqlite3, json, os, time
db='/opt/autoMedia-social-auto-upload/deploy/data/db/database.db'
con=sqlite3.connect(db)
con.row_factory=sqlite3.Row
cur=con.cursor()
print('=== all douyin accounts ===')
for row in cur.execute('SELECT id,type,userName,status,filePath,profile_dir,bound_agent_id,bound_agent_hostname,proxy_url FROM user_info WHERE type=3 ORDER BY id'):
  d=dict(row)
  fp='/opt/autoMedia-social-auto-upload/deploy/data/cookiesFile/'+ (d['filePath'] or '')
  d['cookie_exists']=os.path.exists(fp)
  d['cookie_size']=os.path.getsize(fp) if d['cookie_exists'] else 0
  d['cookie_mtime']=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(fp))) if d['cookie_exists'] else None
  print(json.dumps(d, ensure_ascii=False))
print('=== recent file uploads ===')
for row in cur.execute('SELECT id,filename,filesize,upload_time,file_path FROM file_records ORDER BY id DESC LIMIT 10'):
  print(json.dumps(dict(row), ensure_ascii=False))
PY

echo "=== query publish job via docker ==="
# find listening port
docker port automedia-social-auto-upload 2>/dev/null || true
docker inspect automedia-social-auto-upload --format '{{json .NetworkSettings.Ports}}'

# curl job status from inside docker network
JOB=c9906099-77d3-46a5-837e-3df59d08f13a
curl -s "http://127.0.0.1:5409/publish/jobs/$JOB" 2>/dev/null | head -c 2000; echo
curl -s "http://127.0.0.1:5401/publish/jobs/$JOB" 2>/dev/null | head -c 2000; echo
# try from container
docker exec automedia-social-auto-upload sh -c 'echo PORTS; ss -lntp 2>/dev/null || netstat -lntp 2>/dev/null | head' 2>/dev/null | head -20

echo "=== douyin.log around failures / success markers today ==="
grep -nE "2026-08-13.*(成功|失败|超时|ERROR|WARN|发布完成|上传完成|重试|cookie|登录|歌神|欧鲤|11\\.mp4|钓鱼佬)" /opt/autoMedia-social-auto-upload/deploy/data/logs/douyin.log | tail -100

echo "=== lines after 14:03 ==="
awk '/2026-08-13 14:0/{print}' /opt/autoMedia-social-auto-upload/deploy/data/logs/douyin.log | tail -80

echo "=== cookie sanity for two accounts ==="
python3 - <<'PY'
import json,os
base='/opt/autoMedia-social-auto-upload/deploy/data/cookiesFile'
pairs=[('YOTO欧鲤钓','c2fe38fa-8af1-11f1-a628-6ea8f5bd029d.json'),('渔具厂的歌神','9c93c248-8bf0-11f1-8e90-4e8c12a8480d.json')]
for name,fn in pairs:
  p=os.path.join(base,fn)
  print(name, 'path', fn, 'size', os.path.getsize(p))
  data=json.load(open(p,encoding='utf-8'))
  if isinstance(data,list):
    names=sorted({c.get('name') for c in data if isinstance(c,dict)})
    print('  cookie_count', len(data), 'names_sample', names[:15])
    # sessionid presence
    keys={c.get('name') for c in data if isinstance(c,dict)}
    for k in ['sessionid','sessionid_ss','sid_tt','uid_tt','passport_csrf_token']:
      print(' ', k, 'YES' if k in keys else 'NO')
  elif isinstance(data,dict):
    print('  top_keys', list(data.keys())[:20])
  else:
    print('  type', type(data))
PY
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
