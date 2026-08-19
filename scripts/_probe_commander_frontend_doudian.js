/**
 * Targeted search in Commander web (yoto.work index) + container for 抖店 Agent error.
 */
const { Client } = require('ssh2')
const c = new Client()
c.on('ready', () => {
  const cmd = `
set +e
ROOT=/opt/1panel/www/sites/www.yoto.work/index
echo '=== grep index dist for 抖店 Agent msg ==='
grep -RIn -a --include='*.js' --include='*.html' --include='*.css' '没有读取到抖店\\|抖店助手\\|没有读取到' "$ROOT" 2>/dev/null | head -50
echo '=== grep doudian/抖店 in AutoUpload-ish assets ==='
grep -RIn -a --include='*.js' 'doudian\\|抖店 Agent\\|platformOptions\\|product_issue' "$ROOT/assets" 2>/dev/null | head -40
echo '=== list douyin dir ==='
ls -la "$ROOT/douyin" 2>/dev/null | head -30
grep -RIn -a --include='*.js' --include='*.html' '没有读取到\\|抖店助手\\|抖店 Agent' "$ROOT/douyin" 2>/dev/null | head -30
echo '=== docker exec strings on binary if any ==='
docker exec commander-server-t260220 sh -c 'ls -la /apps 2>/dev/null; ls -la / 2>/dev/null | head; find /apps -maxdepth 3 -type f 2>/dev/null | head -40'
echo '=== strings in commander image for 抖店 ==='
docker exec commander-server-t260220 sh -c "grep -RIn -a '没有读取到\\|抖店助手\\|doudian' /apps 2>/dev/null | head -40"
echo '=== API routes mentioning platform ==='
docker exec commander-server-t260220 sh -c "grep -RIn -a 'doudian\\|douyin\\|抖店\\|shop_list\\|product_issue' /apps 2>/dev/null | head -60"
`
  c.exec(cmd, (e, stream) => {
    let o = ''
    stream.on('data', (d) => (o += d))
    stream.stderr.on('data', (d) => (o += d))
    stream.on('close', () => {
      console.log(o)
      c.end()
    })
  })
}).connect({
  host: process.env.CROSSHUB_SSH_HOST || '124.223.27.98',
  username: 'root',
  password: process.env.CROSSHUB_SSH_PASSWORD || 'Hyh3202276686@@@',
})
