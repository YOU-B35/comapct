const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
echo "=== automedia container ==="
docker inspect automedia-social-auto-upload --format '{{.Config.Image}} {{range .Mounts}}{{.Source}}->{{.Destination}};{{end}}' 2>/dev/null
echo "=== automedia logs last 400 lines (filtered) ==="
docker logs automedia-social-auto-upload --since 4h 2>&1 | grep -iE "publish|douyin|timeout|fail|error|歌神|欧鲤|渔具|YOTO|job|upload|video|cookie|login|session|账号" | tail -120
echo "=== automedia raw tail ==="
docker logs automedia-social-auto-upload --since 2h 2>&1 | tail -80
echo "=== nginx proxy to automedia ==="
grep -RIn "automedia\\|sau\\|5409\\|5401\\|social-auto" /opt/1panel/www/sites/www.yoto.work/proxy/ 2>/dev/null | head -40
echo "=== access /sau /publish/jobs today afternoon ==="
grep "13/Aug/2026:1[3-4]" /opt/1panel/www/sites/www.yoto.work/log/access.log | grep -iE "/sau/|/publish|/material|/upload|/account|/job" | awk '{print $4,$7,$9,$10}' | tail -100
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
