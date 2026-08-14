const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
docker exec automedia-social-auto-upload sh -c "sed -n '460,520p' /app/myUtils/login_agent_hub.py; echo '---'; sed -n '1,80p' /app/utils/account_agent_bind.py 2>/dev/null; ls /app/utils/account_agent_bind.py"
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
