const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = [
    'docker inspect automedia-social-auto-upload --format "Memory={{.HostConfig.Memory}} MemorySwap={{.HostConfig.MemorySwap}} RestartCount={{.RestartCount}} OOM={{.State.OOMKilled}}"',
    'docker stats automedia-social-auto-upload --no-stream --format "CPU={{.CPUPerc}} MEM={{.MemUsage}} PIDs={{.PIDs}}"',
    'ls /opt/autoMedia-social-auto-upload/deploy 2>/dev/null | head',
    'grep -nE "mem|memory|18302|5409" /opt/autoMedia-social-auto-upload/deploy/docker-compose.yml 2>/dev/null | head -40',
    'grep -RIn "18302|automedia.yoto" /opt/1panel/www/sites/www.yoto.work/proxy/ 2>/dev/null | head -30',
    'docker exec crosshub-java printenv | grep -iE "SAU|AUTOMEDIA" || true',
    'grep -nE "sau|18302|automedia" /data/crosshub/docker-compose.yml 2>/dev/null',
    'dmesg -T 2>/dev/null | grep -i oom | tail -10 || journalctl -k --since "2 days ago" 2>/dev/null | grep -i oom | tail -10'
  ].join('; echo; ');
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD,readyTimeout:60000});
