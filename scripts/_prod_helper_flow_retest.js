/**
 * Prod Helper flow smoke: bind → heartbeat → restart stability.
 */
const { spawnSync, spawn } = require('child_process')
const fs = require('fs')
const path = require('path')
const http = require('http')

const ROOT = path.resolve(__dirname, '..')
const BASE = 'https://www.yoto.work'
const ACCOUNT = process.env.CROSSHUB_TEST_ACCOUNT || 'HangZhouYiTuo'
const PASSWORD = process.env.CROSSHUB_TEST_PASSWORD || 'HangZhouYiTuo'
const CONFIG = path.join(ROOT, 'backend', 'python', '.sync-helper-local', 'config.json')
const ENTRY = path.join(ROOT, 'backend', 'python', 'scripts', 'sync_helper_app.py')
const PYROOT = path.join(ROOT, 'backend', 'python')
const results = []

function record(step, ok, detail = '') {
  results.push({ step, ok, detail: String(detail).slice(0, 220) })
  console.log(`[${ok ? 'PASS' : 'FAIL'}] ${step} — ${String(detail).slice(0, 180)}`)
}

async function jfetch(url, opts = {}) {
  const res = await fetch(url, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
  })
  const text = await res.text()
  let body = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = { raw: text.slice(0, 120) }
  }
  return { res, body }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

function httpGet(url, timeoutMs = 4000) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: timeoutMs }, (res) => {
      let data = ''
      res.on('data', (c) => (data += c))
      res.on('end', () => resolve({ ok: res.statusCode >= 200 && res.statusCode < 500, status: res.statusCode, data }))
    })
    req.on('error', () => resolve({ ok: false, status: 0, data: '' }))
    req.on('timeout', () => {
      req.destroy()
      resolve({ ok: false, status: 0, data: '' })
    })
  })
}

function killHelpers() {
  spawnSync(
    'powershell',
    [
      '-NoProfile',
      '-Command',
      `Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'CrossHub-Sync-Helper' -or ($_.CommandLine -and $_.CommandLine -match 'sync_helper_app\\.py') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }`,
    ],
    { encoding: 'utf8' },
  )
}

function writeProdConfig(extra = {}) {
  let prev = {}
  try {
    prev = JSON.parse(fs.readFileSync(CONFIG, 'utf8'))
  } catch {
    /* ignore */
  }
  const cfg = {
    ...prev,
    java_api_url: BASE,
    allow_local_java: false,
    start_ziniao: false,
    health_port: 18765,
    display_name: 'prod-flow-test',
    ...extra,
  }
  fs.mkdirSync(path.dirname(CONFIG), { recursive: true })
  fs.writeFileSync(CONFIG, JSON.stringify(cfg, null, 2), 'utf8')
  return cfg
}

function startHelper() {
  const child = spawn('py', ['-u', ENTRY], {
    cwd: PYROOT,
    env: {
      ...process.env,
      PYTHONPATH: PYROOT,
      JAVA_API_URL: BASE,
      CROSSHUB_HELPER_CONFIG: CONFIG,
      CROSSHUB_START_ZINIAO: '0',
      CROSSHUB_ALLOW_LOCAL_JAVA: '',
    },
    detached: true,
    stdio: 'ignore',
    windowsHide: true,
  })
  child.unref()
  return child.pid
}

async function waitHealth(attempts = 30) {
  for (let i = 0; i < attempts; i++) {
    const h = await httpGet('http://127.0.0.1:18765/health')
    if (h.ok && /ok/i.test(h.data)) return true
    await sleep(500)
  }
  return false
}

async function panelBind() {
  const r = await httpGet('http://127.0.0.1:18766/api/bind')
  try {
    return JSON.parse(r.data)
  } catch {
    return { ok: false, raw: r.data }
  }
}

async function panelStatus() {
  const r = await httpGet('http://127.0.0.1:18766/api/status')
  try {
    return JSON.parse(r.data)
  } catch {
    return { ok: false, raw: r.data }
  }
}

async function main() {
  // A) zip integrity
  {
    const res = await fetch(`${BASE}/crosshub/downloads/CrossHub-Sync-Helper.zip`, { method: 'HEAD' })
    const len = Number(res.headers.get('content-length') || 0)
    const type = res.headers.get('content-type') || ''
    record('helper_zip_head', res.ok && len > 50_000_000 && /zip/i.test(type), `HTTP ${res.status} type=${type} len=${len}`)
  }

  // B) clean restart cold start
  killHelpers()
  await sleep(1500)
  writeProdConfig({
    agent_token: undefined,
    tenant_id: undefined,
    agent_tenant_id: undefined,
    user_id: undefined,
    bound_user_id: undefined,
    machine_fingerprint: undefined,
  })
  // clear bind fields explicitly
  writeProdConfig({
    agent_token: '',
    tenant_id: null,
    user_id: null,
  })
  const pid1 = startHelper()
  const healthy1 = await waitHealth()
  record('cold_start_health', healthy1, `pid=${pid1}`)
  const bind1 = await panelBind()
  const live1 = String(bind1.live_java_api_url || bind1.java_api_url || '')
  record('cold_start_targets_prod', /yoto\.work/i.test(live1), `live=${live1} bound=${bind1.bound}`)
  const st1 = await panelStatus()
  record(
    'cold_start_no_crash_loop',
    st1.agent_status === 'running' || st1.agent_status === 'idle' || !st1.last_error || !/traceback/i.test(String(st1.last_error)),
    `status=${st1.agent_status} err=${String(st1.last_error || '').slice(0, 100)}`,
  )

  // C) login + bind-code + enroll
  const login = await jfetch(`${BASE}/api/auth/login`, {
    method: 'POST',
    body: JSON.stringify({ account: ACCOUNT, password: PASSWORD, portalRole: 'boss' }),
  })
  const token = login.body?.data?.token || ''
  record('prod_login', Boolean(login.res.ok && token), `tenant=${login.body?.data?.tenant_id}`)
  if (!token) return finish(2)
  const auth = { Authorization: `Bearer ${token}` }

  const bc = await jfetch(`${BASE}/api/agent/me/bind-code`, { method: 'POST', headers: auth, body: '{}' })
  const code = bc.body?.data?.code || ''
  record('create_bind_code', Boolean(bc.res.ok && code), `ttl=${bc.body?.data?.expires_in_seconds}`)
  if (!code) return finish(3)

  const py = `
import json, sys
sys.path.insert(0, r${JSON.stringify(PYROOT)})
from agent.bind import consume_bind_code
r = consume_bind_code(${JSON.stringify(code)}, display_name="prod-flow-test", base_url=${JSON.stringify(BASE)}, config_path=r${JSON.stringify(CONFIG)})
print(json.dumps({"ok": True, "tenant_id": r.get("tenant_id"), "java_api_url": r.get("java_api_url")}))
`
  const run = spawnSync('py', ['-c', py], { encoding: 'utf8', cwd: ROOT })
  let parsed = null
  try {
    parsed = JSON.parse((run.stdout || '').trim().split('\n').pop())
  } catch {
    parsed = null
  }
  record('helper_bind', Boolean(run.status === 0 && parsed?.ok), parsed ? JSON.stringify(parsed) : (run.stderr || run.stdout || '').slice(0, 180))

  // restart after bind (simulates user reopen)
  killHelpers()
  await sleep(1500)
  writeProdConfig({ allow_local_java: false, java_api_url: BASE })
  const pid2 = startHelper()
  const healthy2 = await waitHealth()
  record('restart_after_bind_health', healthy2, `pid=${pid2}`)
  const bind2 = await panelBind()
  record(
    'restart_keeps_prod_bind',
    Boolean(bind2.bound) && /yoto\.work/i.test(String(bind2.live_java_api_url || '')),
    `bound=${bind2.bound} live=${bind2.live_java_api_url}`,
  )

  // D) online within 60s
  let online = false
  for (let i = 1; i <= 12; i++) {
    const st = await jfetch(`${BASE}/api/agent/me/status`, { headers: auth })
    online = Boolean(st.body?.data?.online)
    if (online) {
      record('agent_online', true, `attempt=${i} agents=${(st.body?.data?.agents || []).length}`)
      break
    }
    await sleep(5000)
  }
  if (!online) record('agent_online', false, 'not online in 60s')

  // E) status should not stay in error after online
  await sleep(3000)
  const st3 = await panelStatus()
  const err = String(st3.last_error || '')
  record(
    'helper_status_healthy',
    st3.agent_status !== 'error' && !/401/.test(err),
    `status=${st3.agent_status} live=${st3.live_java_api_url} err=${err.slice(0, 120)}`,
  )

  // F) session APIs
  for (const p of ['/api/temu/session', '/api/douyin/session']) {
    const { res, body } = await jfetch(`${BASE}${p}`, { headers: auth })
    record(`api ${p}`, res.status < 500, `HTTP ${res.status} ready=${body?.data?.ready ?? body?.data?.sessions?.[0]?.ready}`)
  }

  // G) second restart stress
  killHelpers()
  await sleep(1200)
  startHelper()
  const healthy3 = await waitHealth()
  const bind3 = await panelBind()
  record(
    'second_restart_stable',
    healthy3 && Boolean(bind3.bound) && /yoto\.work/i.test(String(bind3.live_java_api_url || '')),
    `health=${healthy3} bound=${bind3.bound} live=${bind3.live_java_api_url}`,
  )

  finish(results.some((r) => !r.ok) ? 1 : 0)
}

function finish(code) {
  console.log('\n=== SUMMARY ===')
  for (const r of results) console.log(`${r.ok ? 'OK' : 'NG'} | ${r.step} | ${r.detail}`)
  console.log(`total=${results.length} fail=${results.filter((r) => !r.ok).length}`)
  process.exit(code)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
