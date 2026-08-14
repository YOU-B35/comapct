const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
echo "=== file logs dir ==="
ls -la /opt/autoMedia-social-auto-upload/deploy/data/logs/ 2>/dev/null | tail -20
echo "=== grep account names in logs ==="
grep -RIn "歌神\\|欧鲤\\|渔具\\|YOTO\\|c9906099\\|timeout\\|超时\\|publish" /opt/autoMedia-social-auto-upload/deploy/data/logs/ 2>/dev/null | tail -80
echo "=== db files ==="
ls -la /opt/autoMedia-social-auto-upload/deploy/data/db/ 2>/dev/null
echo "=== cookies accounts ==="
ls -la /opt/autoMedia-social-auto-upload/deploy/data/cookiesFile/ 2>/dev/null | head -40
echo "=== query job from sqlite if exists ==="
DB=$(find /opt/autoMedia-social-auto-upload/deploy/data/db -type f \\( -name '*.db' -o -name '*.sqlite*' \\) 2>/dev/null | head -5)
echo DBs=$DB
for f in $DB; do
  echo "-- $f"
  sqlite3 "$f" ".tables" 2>/dev/null | tr ' ' '\\n' | head -40
done
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
