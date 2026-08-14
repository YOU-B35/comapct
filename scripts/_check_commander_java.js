const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = [
    'curl -s -o /dev/null -w "java_health=%{http_code}\\n" http://127.0.0.1:18080/api/health || true',
    'docker exec crosshub-java printenv CROSSHUB_COMMANDER_USERNAME >/dev/null && echo USERNAME=SET || echo USERNAME=MISSING',
    'docker logs crosshub-java 2>&1 | grep -i commander | tail -8',
    'docker logs crosshub-java 2>&1 | grep -i "Started CrosshubApplication" | tail -3'
  ].join('; ');
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
