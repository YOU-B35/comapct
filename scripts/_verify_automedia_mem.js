const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  c.exec('docker inspect automedia-social-auto-upload --format "Memory={{.HostConfig.Memory}} NanoCPUs={{.HostConfig.NanoCpus}} Status={{.State.Status}}"; docker stats automedia-social-auto-upload --no-stream --format "CPU={{.CPUPerc}} MEM={{.MemUsage}} PIDs={{.PIDs}}"; curl -s -o /dev/null -w "api=%{http_code} t=%{time_total}\\n" --max-time 8 http://127.0.0.1:18302/api/  || true', (e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
