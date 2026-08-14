const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
echo "=== automedia compose/mem limit ==="
docker inspect automedia-social-auto-upload --format 'Memory={{.HostConfig.Memory}} NanoCPUs={{.HostConfig.NanoCpus}} MemorySwap={{.HostConfig.MemorySwap}}'
find /opt/autoMedia-social-auto-upload /data -name 'docker-compose*.yml' 2>/dev/null | head -10
ls /opt/autoMedia-social-auto-upload/deploy 2>/dev/null | head
grep -RIn "mem_limit\\|memory:\\|18302\\|5409\\|automedia" /opt/autoMedia-social-auto-upload/deploy/*.yml /opt/autoMedia-social-auto-upload/deploy/docker-compose*.yml 2>/dev/null | head -40
echo "=== nginx paths to 18302 ==="
grep -RIn "18302\\|autoMedia\\|automedia\\|login-agent\\|getValidAccounts" /opt/1panel/www/sites/www.yoto.work/proxy/ /opt/1panel/www/sites/www.yoto.work/index/ 2>/dev/null | grep -v assets | head -40
echo "=== chromium/playwright procs in container ==="
docker exec automedia-social-auto-upload sh -c 'ps aux 2>/dev/null | head -5; echo ---; ps aux 2>/dev/null | grep -ciE "chrom|playwright|python|flask"; echo MEMINFO; cat /sys/fs/cgroup/memory.max 2>/dev/null; cat /sys/fs/cgroup/memory.current 2>/dev/null; cat /sys/fs/cgroup/memory.peak 2>/dev/null'
echo "=== dmesg OOM recent ==="
dmesg -T 2>/dev/null | grep -iE "oom|killed process|automedia" | tail -20
echo "=== java -> automedia config ==="
docker exec crosshub-java printenv | grep -iE "SAU|AUTOMEDIA|18302" || true
grep -RIn "18302\\|sau\\|automedia" /data/crosshub/docker-compose.yml /data/crosshub/*.env 2>/dev/null | head -20
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
