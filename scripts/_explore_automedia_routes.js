const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
APP=/opt/autoMedia-social-auto-upload/app
echo "=== account routes ==="
grep -RIn "route\\|@app.\\|/account\\|login-agent\\|activate\\|bound_agent" $APP --include='*.py' 2>/dev/null | grep -iE "route|account|login.agent|rebind|bound" | head -80
echo "=== find flask blueprints ==="
ls $APP/*.py 2>/dev/null | head
grep -n "Blueprint\\|register_blueprint\\|/login-agent\\|/account" $APP/sau_backend.py 2>/dev/null | head -40
ls $APP/myUtils 2>/dev/null | head -40
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
