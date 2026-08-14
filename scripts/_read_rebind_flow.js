const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
docker exec automedia-social-auto-upload sh -c "grep -n 'refresh_bound\\|set_account_bound\\|kind.*login\\|换绑\\|clear.*bound\\|bound_agent' /app/myUtils/login_agent_hub.py /app/myUtils/login_agent_service.py 2>/dev/null | head -60"
docker exec automedia-social-auto-upload sh -c "sed -n '510,620p' /app/myUtils/login_agent_hub.py"
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
