const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = [
    'echo "=== full hyhacct-image.conf (redact auth) ==="',
    'sed -E "s/(Authorization: Bearer )[^\\"]+/\\1***REDACTED***/g; s/(sk-[A-Za-z0-9]+)/sk-***REDACTED***/g" /opt/1panel/www/sites/www.yoto.work/proxy/hyhacct-image.conf',
    'echo "=== nginx upstream errors today around edits ==="',
    'grep -E "13/Aug/2026:11:|upstream|api.hyhacct|api-proxy" /opt/1panel/www/sites/www.yoto.work/log/error.log | grep -v "404.html" | tail -60',
    'echo "=== today edits summary ==="',
    'grep "13/Aug/2026" /opt/1panel/www/sites/www.yoto.work/log/access.log | grep "api-proxy/images/" | awk \'{print $4,$7,$9,$10}\'',
    'echo "=== sample body sizes meaning ==="',
    'echo "502 bodies are typically upstream error JSON passed/mapped by nginx"'
  ].join('\n');
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
