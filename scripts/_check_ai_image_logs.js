const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = [
    'echo "=== hyhacct-image.conf ==="',
    'cat /opt/1panel/www/sites/www.yoto.work/proxy/hyhacct-image.conf 2>/dev/null || echo MISSING',
    'echo "=== nginx conf snippets mentioning api-proxy/hyhacct ==="',
    'grep -RIn "api-proxy\\|hyhacct\\|images/edits\\|images/generations" /opt/1panel/www/sites/www.yoto.work/ 2>/dev/null | head -40',
    'echo "=== recent access logs (api-proxy / images) ==="',
    'ACCESS=$(ls -1t /opt/1panel/www/sites/www.yoto.work/log/access*.log 2>/dev/null | head -1); echo ACCESS=$ACCESS',
    'ERRORL=$(ls -1t /opt/1panel/www/sites/www.yoto.work/log/error*.log 2>/dev/null | head -1); echo ERRORL=$ERRORL',
    'if [ -n "$ACCESS" ]; then grep -E "api-proxy|/v1/images|hyhacct|images/edits|images/generations" "$ACCESS" | tail -80; fi',
    'echo "=== recent error logs ==="',
    'if [ -n "$ERRORL" ]; then grep -iE "api-proxy|hyhacct|images|upstream|404" "$ERRORL" | tail -40; fi',
    'echo "=== docker/java logs ai ==="',
    'docker logs crosshub-java --since 6h 2>&1 | grep -iE "ai.image|hyhacct|images/|gpt-image|download generated" | tail -30 || true'
  ].join('\n');
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
