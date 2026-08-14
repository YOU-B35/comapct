const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  c.exec(`grep 'api-proxy/images' /opt/1panel/www/sites/www.yoto.work/log/access.log | tail -15 | awk '{print $4,$7,$9,$10}'; echo '---15/16 counts---'; grep -E '13/Aug/2026:1[56]:' /opt/1panel/www/sites/www.yoto.work/log/access.log | grep 'api-proxy/images' | awk '{print $9}' | sort | uniq -c | sort -nr`, (e,stream)=>{
    stream.on('data',d=>process.stdout.write(d));
    stream.stderr.on('data',d=>process.stderr.write(d));
    stream.on('close',()=>c.end());
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
