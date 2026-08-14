const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
echo "=== host ==="
hostname; date; uptime
echo "=== memory/disk ==="
free -h
df -h / /data /opt 2>/dev/null | sed -n '1,10p'
echo "=== docker ps ==="
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | head -40
echo "=== key containers resources ==="
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.PIDs}}' crosshub-java crosshub-express automedia-social-auto-upload 1Panel-openresty-UN3Y 2>/dev/null
echo "=== health probes ==="
curl -s -o /dev/null -w 'java_18080=%{http_code} t=%{time_total}\\n' --max-time 8 http://127.0.0.1:18080/api/health || echo java_fail
curl -s -o /dev/null -w 'express_18081=%{http_code} t=%{time_total}\\n' --max-time 8 http://127.0.0.1:18081/api/health || echo express_fail
curl -s -o /dev/null -w 'automedia_18302=%{http_code} t=%{time_total}\\n' --max-time 8 http://127.0.0.1:18302/ || echo automedia_fail
curl -s -o /dev/null -w 'site_crosshub=%{http_code} t=%{time_total}\\n' --max-time 10 https://www.yoto.work/crosshub/ || echo site_fail
curl -s https://www.yoto.work/crosshub/ 2>/dev/null | grep -o 'index-[^"]*\\.js' | head -1
echo "=== automedia mem limit ==="
docker inspect automedia-social-auto-upload --format 'MemLimit={{.HostConfig.Memory}} Status={{.State.Status}} OOM={{.State.OOMKilled}} Restart={{.RestartCount}} Started={{.State.StartedAt}}' 2>/dev/null
docker inspect crosshub-java --format 'Status={{.State.Status}} OOM={{.State.OOMKilled}} Restart={{.RestartCount}} Started={{.State.StartedAt}}' 2>/dev/null
echo "=== load / top mem ==="
ps aux --sort=-%mem | awk 'NR==1||NR<=8{print}'
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
