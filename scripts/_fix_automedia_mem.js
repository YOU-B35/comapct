const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
set -e
COMPOSE=/opt/autoMedia-social-auto-upload/app/deploy/automedia/docker-compose.yml
echo "=== free before ==="
free -h
echo "=== compose before ==="
cat "$COMPOSE"
cp -a "$COMPOSE" "$COMPOSE.bak.$(date +%Y%m%d%H%M%S)"
python3 - <<'PY'
from pathlib import Path
p=Path('/opt/autoMedia-social-auto-upload/app/deploy/automedia/docker-compose.yml')
text=p.read_text(encoding='utf-8')
# normalize common keys
import re
# Ensure deploy.resources or mem_limit
if 'mem_limit' in text or 'memory:' in text:
    text2=re.sub(r'(mem_limit:\\s*)[^\\n]+', r'\\g<1>3g', text)
    text2=re.sub(r'(memory:\\s*)[^\\n]+', r'\\g<1>3G', text2)
    # also memory swap if present
    text2=re.sub(r'(memswap_limit:\\s*)[^\\n]+', r'\\g<1>3.5g', text2)
else:
    # inject under service app:
    lines=text.splitlines(True)
    out=[]
    injected=False
    for i,line in enumerate(lines):
        out.append(line)
        if (not injected) and re.match(r'^\\s{2}app:\\s*$', line):
            # look ahead - inject after image/container_name block start with mem at service level
            pass
    text2=text
    if re.search(r'^\\s{2}app:\\s*$', text, re.M):
        text2=re.sub(r'(^\\s{2}app:\\s*\\n)', r'\\1    mem_limit: 3g\\n    memswap_limit: 3584m\\n', text, count=1, flags=re.M)
    else:
        raise SystemExit('cannot find app service')
if text2==text and '3g' not in text2.lower() and '3G' not in text2:
    # force replace any 1280m / 1.25g patterns
    text2=re.sub(r'mem_limit:\\s*[^\\n]+', 'mem_limit: 3g', text)
    if 'mem_limit:' not in text2:
        text2=re.sub(r'(^\\s{2}app:\\s*\\n)', r'\\1    mem_limit: 3g\\n    memswap_limit: 3584m\\n', text, count=1, flags=re.M)
p.write_text(text2, encoding='utf-8')
print('UPDATED')
print(text2)
PY
cd /opt/autoMedia-social-auto-upload/app/deploy/automedia
docker compose up -d --force-recreate app
sleep 8
docker inspect automedia-social-auto-upload --format 'Memory={{.HostConfig.Memory}} MemorySwap={{.HostConfig.MemorySwap}} Status={{.State.Status}} OOM={{.State.OOMKilled}}'
docker stats automedia-social-auto-upload --no-stream --format 'CPU={{.CPUPerc}} MEM={{.MemUsage}} PIDs={{.PIDs}}'
curl -s -o /dev/null -w 'health_18302=%{http_code} t=%{time_total}\\n' --max-time 10 http://127.0.0.1:18302/ || echo health_fail
echo "=== free after ==="
free -h
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',(code)=>{console.log(o);c.end();process.exit(code||0);});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
