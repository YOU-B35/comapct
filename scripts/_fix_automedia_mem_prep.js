const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
set -e
echo "=== locate compose / run config ==="
find /opt/autoMedia-social-auto-upload /root /data -maxdepth 4 \\( -name 'docker-compose*.yml' -o -name 'compose*.yml' \\) 2>/dev/null | head -20
docker inspect automedia-social-auto-upload --format 'Name={{.Name}} Image={{.Config.Image}} WorkingDir={{.Config.Labels}}'
# 1panel often stores compose under /opt/1panel
find /opt/1panel -iname '*automedia*' 2>/dev/null | head -30
find /opt/1panel -iname '*autoMedia*' 2>/dev/null | head -30
ls -la /opt/autoMedia-social-auto-upload/ 2>/dev/null | head -30
ls -la /opt/autoMedia-social-auto-upload/deploy/ 2>/dev/null
# show HostConfig recreate-able fields
docker inspect automedia-social-auto-upload --format '{{json .HostConfig}}' | python3 -c "import sys,json; h=json.load(sys.stdin); print({k:h.get(k) for k in ['Memory','MemorySwap','NanoCpus','CpuShares','Binds','PortBindings','RestartPolicy','NetworkMode','Privileged']})"
docker inspect automedia-social-auto-upload --format '{{json .Config.Env}}' | head -c 1500; echo
docker inspect automedia-social-auto-upload --format '{{json .Mounts}}'
docker inspect automedia-social-auto-upload --format '{{range .NetworkSettings.Networks}}{{.NetworkID}} {{.IPAddress}}{{end}}'
docker network ls
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
