const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
echo "=== automedia container health ==="
docker ps -a --filter name=automedia --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo "=== restart count / OOM ==="
docker inspect automedia-social-auto-upload --format 'RestartCount={{.RestartCount}} Status={{.State.Status}} OOM={{.State.OOMKilled}} StartedAt={{.State.StartedAt}} FinishedAt={{.State.FinishedAt}} Health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}'
echo "=== resource usage ==="
docker stats automedia-social-auto-upload --no-stream --format 'CPU={{.CPUPerc}} MEM={{.MemUsage}} PIDs={{.PIDs}}'
echo "=== nginx sau proxy ==="
sed -n '110,160p' /opt/1panel/www/sites/www.yoto.work/proxy/crosshub.conf
echo "=== recent 502/504/499 on sau/automedia paths ==="
grep "13/Aug/2026" /opt/1panel/www/sites/www.yoto.work/log/access.log | grep -E "/api/sau|/sau/|/login-agent|/publish|/account|/getFile|/upload" | grep -E " (499|500|502|503|504|408) " | tail -40
echo "=== latency samples today GET /api/sau/token and account ==="
grep "13/Aug/2026" /opt/1panel/www/sites/www.yoto.work/log/access.log | grep -E "/api/sau/token|/login-agent/status|POST /account|GET /getValidAccounts|GET /login-agent" | awk '{print $4,$7,$9,$10,$NF}' | tail -50
echo "=== automedia error log snippets last 3h ==="
docker logs automedia-social-auto-upload --since 3h 2>&1 | grep -iE "error|timeout|traceback|exception|killed|oom|worker|busy|reject|502|503" | grep -v download | tail -50
echo "=== java sau bridge logs ==="
docker logs crosshub-java --since 6h 2>&1 | grep -iE "sau|automedia|18302|timeout|connect" | tail -30
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
