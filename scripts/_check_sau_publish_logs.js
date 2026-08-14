const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = [
    'echo "=== today access: sau/automedia/publish/douyin ==="',
    'grep -E "13/Aug/2026:(1[2-4]|[0-9]{2})" /opt/1panel/www/sites/www.yoto.work/log/access.log | grep -iE "sau|automedia|publish|douyin|/api/content|/api/account|material|upload" | awk \'{print $4,$7,$9,$10}\' | tail -80',
    'echo "=== recent 502/504/499 around publish ==="',
    'grep "13/Aug/2026" /opt/1panel/www/sites/www.yoto.work/log/access.log | grep -iE "sau|automedia|publish|material|upload|content" | grep -E " (499|502|504|500|408) " | tail -40',
    'echo "=== java logs sau/publish today ==="',
    'docker logs crosshub-java --since 6h 2>&1 | grep -iE "sau|automedia|publish|douyin|timeout|渔具|欧鲤|歌神" | tail -60 || true',
    'echo "=== express/docker logs if any ==="',
    'docker ps --format "{{.Names}}" | head -20',
    'ls -la /data/crosshub/ 2>/dev/null | head -30'
  ].join('\n');
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
