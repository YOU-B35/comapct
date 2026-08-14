const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
echo "=== douyin.log today (Aug 13) ==="
grep "2026-08-13" /opt/autoMedia-social-auto-upload/deploy/data/logs/douyin.log | tail -150
echo "=== ERROR/WARN last 80 in douyin.log ==="
grep -E "ERROR|WARN|失败|超时|timeout|歌神|欧鲤" /opt/autoMedia-social-auto-upload/deploy/data/logs/douyin.log | tail -80
echo "=== sqlite tables via python ==="
python3 - <<'PY'
import sqlite3, json
db='/opt/autoMedia-social-auto-upload/deploy/data/db/database.db'
con=sqlite3.connect(db)
con.row_factory=sqlite3.Row
cur=con.cursor()
tables=[r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print('tables', tables)
for t in tables:
  if any(k in t.lower() for k in ['account','user','cookie','publish','job','file','material','video','platform']):
    try:
      cols=[r[1] for r in cur.execute(f'PRAGMA table_info({t})')]
      print(t, 'cols=', cols[:20], 'count=', cur.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0])
    except Exception as e:
      print(t, 'err', e)
# find account names
for t in tables:
  cols=[r[1] for r in cur.execute(f'PRAGMA table_info({t})')]
  name_cols=[c for c in cols if any(x in c.lower() for x in ['name','nick','account','title','cookie','file'])]
  if not name_cols: continue
  q=None
  for c in name_cols:
    try:
      rows=cur.execute(f"SELECT * FROM {t} WHERE CAST({c} AS TEXT) LIKE '%歌神%' OR CAST({c} AS TEXT) LIKE '%欧鲤%' OR CAST({c} AS TEXT) LIKE '%YOTO%' LIMIT 5").fetchall()
      if rows:
        print('HIT', t, c, 'n=', len(rows))
        for row in rows:
          d={k:row[k] for k in row.keys()}
          # redact long
          for k,v in list(d.items()):
            if isinstance(v,str) and len(v)>120: d[k]=v[:120]+'...'
          print(json.dumps(d, ensure_ascii=False)[:500])
    except Exception as e:
      pass
# publish jobs
for t in tables:
  if 'job' in t.lower() or 'publish' in t.lower():
    cols=[r[1] for r in cur.execute(f'PRAGMA table_info({t})')]
    print('JOBTABLE', t, cols)
    try:
      rows=cur.execute(f'SELECT * FROM {t} ORDER BY rowid DESC LIMIT 8').fetchall()
      for row in rows:
        d={k:row[k] for k in row.keys()}
        for k,v in list(d.items()):
          if isinstance(v,str) and len(v)>200: d[k]=v[:200]+'...'
        print(json.dumps(d, ensure_ascii=False)[:800])
    except Exception as e:
      print('job err', e)
PY
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
