const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  c.exec('sed -n "388,520p" /opt/autoMedia-social-auto-upload/app/sau_backend.py', (e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
