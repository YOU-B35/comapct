const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
docker exec automedia-social-auto-upload sh -c "grep -RIn 'bound_agent' /app --include='*.py' 2>/dev/null | head -40"
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
