const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
APP=/opt/autoMedia-social-auto-upload/app
sed -n '672,720p' $APP/sau_backend.py
echo "==== getValidAccounts / getAccounts bound ===="
grep -n "getValidAccounts\\|getAccounts\\|bound_agent\\|userName\\|filePath" $APP/sau_backend.py | head -40
# find account list response builder
grep -RIn "bound_agent_hostname\\|getValidAccounts" $APP --include='*.py' | head -30
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
