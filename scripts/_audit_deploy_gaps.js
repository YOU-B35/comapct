/**
 * Audit deploy gaps. CROSSHUB_SSH_PASSWORD=... node scripts/_audit_deploy_gaps.js
 */
const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')

const ROOT = path.resolve(__dirname, '..')
module.paths.push(path.join(__dirname, 'node_modules'))
const { Client } = require('ssh2')

const host = process.env.CROSSHUB_SSH_HOST || '124.223.27.98'
const password = process.env.CROSSHUB_SSH_PASSWORD
if (!password) {
  console.error('CROSSHUB_SSH_PASSWORD required')
  process.exit(1)
}

function localIndexAsset() {
  const p = path.join(ROOT, 'dev/vue-site/dist/index.html')
  if (!fs.existsSync(p)) return null
  const html = fs.readFileSync(p, 'utf8')
  const m = html.match(/assets\/(index-[^"]+\.js)/)
  return m ? m[1] : null
}

function pythonChanged() {
  return execSync('git diff --name-only 444b00a..HEAD -- backend/python', {
    cwd: ROOT,
    encoding: 'utf8',
  })
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean)
    .filter((p) => !p.includes('/tests/'))
}

function exec(conn, cmd) {
  return new Promise((resolve, reject) => {
    conn.exec(cmd, (err, stream) => {
      if (err) return reject(err)
      let out = ''
      stream.on('data', (d) => {
        out += d
      })
      stream.stderr.on('data', (d) => {
        out += d
      })
      stream.on('close', (code) => resolve({ code, out }))
    })
  })
}

async function main() {
  const expectedIndex = localIndexAsset()
  const jarPath = path.join(ROOT, 'backend/java/target/temu-api-0.1.0.jar')
  const jarSize = fs.existsSync(jarPath) ? fs.statSync(jarPath).size : 0
  const pyFiles = pythonChanged()

  const remoteScript = `
set +e
WEB=/opt/1panel/www/sites/www.yoto.work/index/crosshub
DATA=/data/crosshub
echo FRONTEND_INDEX=$(grep -oE 'index-[^"]+\\.js' "$WEB/index.html" | head -1)
echo FRONTEND_HTML_MTIME=$(stat -c %y "$WEB/index.html" 2>/dev/null)
if [ -n "${expectedIndex || ''}" ] && [ -f "$WEB/assets/${expectedIndex || 'missing'}" ]; then echo FRONTEND_ASSET=OK; else echo FRONTEND_ASSET=MISSING; fi
if [ -f "$WEB/assets/AiImageWorkbench-DVdHBa_p.js" ]; then echo AI_WB=OK; else echo AI_WB=MISSING; fi
echo JAR_SIZE=$(stat -c %s "$DATA/app.jar" 2>/dev/null)
echo JAR_MTIME=$(stat -c %y "$DATA/app.jar" 2>/dev/null)
echo JAVA_STARTED=$(docker inspect -f '{{.State.StartedAt}}' crosshub-java 2>/dev/null)
echo JAVA_RUNNING=$(docker inspect -f '{{.State.Running}}' crosshub-java 2>/dev/null)
echo JAVA_HTTP=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18080/api/health)
echo EXPRESS_STARTED=$(docker inspect -f '{{.State.StartedAt}}' crosshub-express 2>/dev/null)
echo EXPRESS_HTTP=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18081/api/health)
echo EXPRESS_SRC=$(stat -c %y "$DATA/express-src/package.json" 2>/dev/null || echo MISSING)
echo PY_WORKER=$(docker inspect -f '{{.State.Running}}' crosshub-python-worker 2>/dev/null || echo MISSING)
echo PY_SRC=$(stat -c %y "$DATA/python-src" 2>/dev/null || echo MISSING)
if [ -f "$DATA/python-src/app/browser/temu_cookie_trust.py" ]; then echo COOKIE_TRUST=OK; else echo COOKIE_TRUST=MISSING; fi
if [ -f "$DATA/python-src/app/browser/profile_startup.py" ]; then echo PROFILE_STARTUP=OK; else echo PROFILE_STARTUP=MISSING; fi
if [ -f /opt/1panel/www/sites/www.yoto.work/proxy/crosshub-spa.conf ]; then echo SPA_CONF=OK; else echo SPA_CONF=MISSING; fi
if [ -f /opt/1panel/www/sites/www.yoto.work/proxy/crosshub.conf ]; then echo PROXY_CONF=OK; else echo PROXY_CONF=MISSING; fi
if [ -f /opt/1panel/www/sites/www.yoto.work/proxy/hyhacct-image.conf ]; then echo IMAGE_CONF=OK; else echo IMAGE_CONF=MISSING; fi
echo JAR_CLASSES=$(jar tf "$DATA/app.jar" 2>/dev/null | grep -E 'SauBridgeService|TemuAgentService|CommanderProxyService|OpsTeamController|TeamScopeService' | tr '\\n' ' ')
`.trim()

  const conn = new Client()
  await new Promise((resolve, reject) =>
    conn.on('ready', resolve).on('error', reject).connect({
      host,
      username: process.env.CROSSHUB_SSH_USER || 'root',
      password,
      readyTimeout: 120000,
    }),
  )

  // Pass expected index via env substitution locally into script
  const script = remoteScript.replace(
    'FRONTEND_ASSET',
    'FRONTEND_ASSET',
  ).replace(
    `assets/${expectedIndex || 'missing'}`,
    `assets/${expectedIndex || 'missing'}`,
  )

  const { out } = await exec(conn, script)
  console.log(out)

  const lines = Object.fromEntries(
    out
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l.includes('='))
      .map((l) => {
        const i = l.indexOf('=')
        return [l.slice(0, i), l.slice(i + 1)]
      }),
  )

  console.log('\n== local ==')
  console.log('expected_index=', expectedIndex)
  console.log('local_jar_size=', jarSize)
  console.log('python_changed=', pyFiles.length)

  const gaps = []
  if (lines.FRONTEND_INDEX !== expectedIndex) {
    gaps.push(`前端 index 不一致: remote=${lines.FRONTEND_INDEX} local=${expectedIndex}`)
  }
  if (lines.FRONTEND_ASSET === 'MISSING') gaps.push('前端主 bundle 文件缺失')
  if (lines.AI_WB === 'MISSING') gaps.push('AI 生图 AiImageWorkbench 资源缺失')
  if (Number(lines.JAR_SIZE || 0) !== jarSize) {
    gaps.push(`Java jar 大小不一致: remote=${lines.JAR_SIZE} local=${jarSize}`)
  }
  if (!String(lines.JAR_CLASSES || '').includes('SauBridgeService')) gaps.push('远程 jar 未含 SauBridgeService')
  if (!String(lines.JAR_CLASSES || '').includes('TemuAgentService')) gaps.push('远程 jar 未含 TemuAgentService')
  if (lines.COOKIE_TRUST === 'MISSING') gaps.push('服务器 python-src 缺少 temu_cookie_trust.py（Temu cookie 信任）')
  if (lines.PROFILE_STARTUP === 'MISSING') gaps.push('服务器 python-src 缺少 profile_startup.py')
  if (lines.PY_WORKER === 'MISSING' || lines.PY_SRC === 'MISSING') gaps.push('python-worker / python-src 未部署或不可用')
  if (lines.SPA_CONF === 'MISSING') gaps.push('nginx crosshub-spa.conf 缺失')
  if (lines.IMAGE_CONF === 'MISSING') gaps.push('nginx hyhacct-image.conf 缺失（AI 生图代理）')

  // Client-side helper note
  gaps.push('【说明】Sync Helper / agent/*.py 主要跑在用户本机，服务器 python-src 不等于本机 Helper 已更新')

  console.log('\n== 遗漏/风险清单 ==')
  gaps.forEach((g, i) => console.log(`${i + 1}. ${g}`))

  console.log('\n== 本次提交中未随 jar/web 部署的 Python 文件 ==')
  pyFiles.forEach((p) => console.log(' -', p))

  conn.end()
}

main().catch((e) => {
  console.error(e.message || e)
  process.exit(1)
})
