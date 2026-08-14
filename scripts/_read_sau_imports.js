const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  c.exec(`grep -n "from myUtils.login_agent_hub\\|import.*login_agent\\|set_active_agent\\|list_agents\\|sqlite3.connect\\|BASE_DIR\\|resolve_current_user" /opt/autoMedia-social-auto-upload/app/sau_backend.py | head -50; echo ---; ls /opt/autoMedia-social-auto-upload/app/utils/account_agent_bind.py; wc -l /opt/autoMedia-social-auto-upload/app/sau_backend.py`, (e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
