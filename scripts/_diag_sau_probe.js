const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
echo "=== free -h ==="; free -h
echo "=== how container was created ==="
docker inspect automedia-social-auto-upload --format '{{json .Config.Labels}}' | head -c 800; echo
docker inspect automedia-social-auto-upload --format 'Image={{.Config.Image}}'
# chrome count without hanging: use docker top
docker top automedia-social-auto-upload -eo pid,cmd 2>/dev/null | grep -ci chrome || true
docker top automedia-social-auto-upload -eo pid,cmd 2>/dev/null | grep -ci playwright || true
docker top automedia-social-auto-upload -eo pid,cmd 2>/dev/null | wc -l
echo "=== probe token path latency ==="
time curl -s -o /dev/null -w "local_18302=%{http_code} time=%{time_total}\\n" http://127.0.0.1:18302/  || true
time curl -s -o /dev/null -w "automedia_host=%{http_code} time=%{time_total}\\n" https://automedia.yoto.work/api/  --max-time 20 || true
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',()=>{console.log(o);c.end();});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
