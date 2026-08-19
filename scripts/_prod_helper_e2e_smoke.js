/**
 * Production E2E smoke: auth → bind-code → helper bind → agent online → data APIs.
 * Usage:
 *   CROSSHUB_TEST_ACCOUNT=... CROSSHUB_TEST_PASSWORD=... node scripts/_prod_helper_e2e_smoke.js
 */
const { spawnSync } = require('child_process')
const path = require('path')
const fs = require('fs')

const ROOT = path.resolve(__dirname, '..')
const BASE = process.env.CROSSHUB_API_BASE || 'https://www.yoto.work'
const ACCOUNT = process.env.CROSSHUB_TEST_ACCOUNT || ''
const PASSWORD = process.env.CROSSHUB_TEST_PASSWORD || ''
const HELPER_PANEL = 'http://127.0.0.1:18766'
const HELPER_HEALTH = 'http://127.0.0.1:18765/health'
const CONFIG = path.join(ROOT, 'backend', 'python', '.sync-helper-local', 'config.json')

const results = []

function record(step, ok, detail = '') {
  results.push({ step, ok, detail: String(detail || '').slice(0, 240) })
  const mark = ok ? 'PASS' : 'FAIL'
  console.log(`[${mark}] ${step}${detail ? ` — ${String(detail).slice(0, 180)}` : ''}`)
}

async function jfetch(url, opts = {}) {
  const res = await fetch(url, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    },
  })
  const text = await res.text()
  let body = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = { raw: text.slice(0, 200) }
  }
  return { res, body, text }
}

function redact(s) {
  return String(s || '')
    .replace(/eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+/g, '[JWT]')
    .replace(/[0-9a-f]{8}-[0-9a-f-]{20,}/gi, '[UUID]')
    .replace(/"agent_token"\s*:\s*"[^"]+"/g, '"agent_token":"[REDACTED]"')
}

async function main() {
  if (!ACCOUNT || !PASSWORD) {
    throw new Error('CROSSHUB_TEST_ACCOUNT / CROSSHUB_TEST_PASSWORD required')
  }

  // 1) public assets
  {
    const zip = await fetch(`${BASE}/crosshub/downloads/CrossHub-Sync-Helper.zip`, { method: 'HEAD' })
    record('helper_zip_download', zip.ok && zip.headers.get('content-type')?.includes('zip'), `HTTP ${zip.status} len=${zip.headers.get('content-length')}`)
    const health = await jfetch(`${BASE}/api/health`)
    record('api_health', health.res.ok && health.body?.success === true, JSON.stringify(health.body))
  }

  // 2) local helper process
  {
    const h = await fetch(HELPER_HEALTH).catch(() => null)
    const ok = Boolean(h && h.ok)
    record('local_helper_health', ok, ok ? await h.text() : 'unreachable')
    if (!ok) {
      printSummary()
      process.exit(2)
    }
  }

  // 3) login prod
  let token = ''
  let tenantId = null
  {
    const { res, body } = await jfetch(`${BASE}/api/auth/login`, {
      method: 'POST',
      body: JSON.stringify({ account: ACCOUNT, password: PASSWORD, portalRole: 'boss' }),
    })
    const data = body?.data || body || {}
    token = data.token || data.accessToken || data.jwt || ''
    if (!token && body?.code === 0) token = body?.data?.token || ''
    // common shapes
    if (!token) token = body?.token || ''
    tenantId = data.tenantId ?? data.tenant_id ?? body?.data?.tenantId
    record('prod_login', Boolean(res.ok && token), `HTTP ${res.status} tenant=${tenantId ?? '?'} keys=${Object.keys(data || {}).join(',')}`)
    if (!token) {
      console.log('login_body=', redact(JSON.stringify(body)).slice(0, 500))
      printSummary()
      process.exit(3)
    }
  }

  const auth = { Authorization: `Bearer ${token}` }

  // 4) bind code
  let code = ''
  {
    const { res, body } = await jfetch(`${BASE}/api/agent/me/bind-code`, {
      method: 'POST',
      headers: auth,
      body: '{}',
    })
    const data = body?.data || body || {}
    code = data.code || ''
    record('create_bind_code', Boolean(res.ok && code), `HTTP ${res.status} ttl=${data.expires_in_seconds || '?'}`)
    if (!code) {
      printSummary()
      process.exit(4)
    }
  }

  // 5) clear + bind helper to prod via Python (panel currently may target local java)
  {
    try {
      await fetch(`${HELPER_PANEL}/api/bind`, { method: 'DELETE' })
    } catch {
      /* ignore */
    }
    const py = `
import json, sys
sys.path.insert(0, r${JSON.stringify(path.join(ROOT, 'backend', 'python'))})
from agent.bind import consume_bind_code, binding_status
r = consume_bind_code(${JSON.stringify(code)}, display_name="prod-e2e-smoke", base_url=${JSON.stringify(BASE)}, config_path=r${JSON.stringify(CONFIG)})
print(json.dumps({"ok": True, "tenant_id": r.get("tenant_id"), "user_id": r.get("user_id"), "java_api_url": r.get("java_api_url")}))
`
    const run = spawnSync('py', ['-c', py], { encoding: 'utf8', cwd: ROOT })
    let parsed = null
    try {
      parsed = JSON.parse((run.stdout || '').trim().split('\n').pop())
    } catch {
      parsed = null
    }
    const ok = run.status === 0 && parsed?.ok && /yoto\.work/i.test(String(parsed.java_api_url || ''))
    record(
      'helper_bind_prod',
      ok,
      ok
        ? `tenant=${parsed.tenant_id} user=${parsed.user_id} api=${parsed.java_api_url}`
        : redact(`${run.stderr || run.stdout || 'bind failed'}`),
    )
    if (!ok) {
      printSummary()
      process.exit(5)
    }
  }

  // 6) restart helper heartbeat toward prod — poke panel status; may need process already polling
  {
    // Ensure config points to prod
    const cfg = JSON.parse(fs.readFileSync(CONFIG, 'utf8'))
    cfg.java_api_url = BASE
    fs.writeFileSync(CONFIG, JSON.stringify(cfg, null, 2), 'utf8')

    // Try to start/restart via ensuring bind start endpoint isn't available; kill+relaunch local helper script if present
    const ensure = path.join(ROOT, 'scripts', 'ensure-local-helper.ps1')
    if (fs.existsSync(ensure)) {
      // Do NOT use ensure-local-helper if it forces localhost — check quickly
      const src = fs.readFileSync(ensure, 'utf8')
      if (!/18080/.test(src) || /yoto\.work/.test(src)) {
        /* leave running */
      }
    }

    // Hot path: call consume already wrote token; ask tray to reload by POSTing bind again is noop.
    // Soft-check panel bind status
    await new Promise((r) => setTimeout(r, 2000))
    const st = await jfetch(`${HELPER_PANEL}/api/bind`)
    record(
      'helper_panel_bind_status',
      Boolean(st.body?.bound || st.body?.ok === true || st.body?.tenant_id),
      redact(JSON.stringify(st.body)).slice(0, 220),
    )
  }

  // 7) wait for agent online on prod
  let online = false
  for (let i = 0; i < 12; i++) {
    const { res, body } = await jfetch(`${BASE}/api/agent/me/status`, { headers: auth })
    const data = body?.data || body || {}
    online = Boolean(data.online || data.agent_online)
    if (online) {
      record('agent_online_prod', true, `attempt=${i + 1} agents=${(data.agents || []).length}`)
      break
    }
    await new Promise((r) => setTimeout(r, 5000))
  }
  if (!online) {
    record('agent_online_prod', false, 'helper bound but heartbeat not seen on prod within 60s — may need restart Sync Helper process')
  }

  // 8) platform session / data endpoints (read-only)
  const probes = [
    ['GET', '/api/temu/session'],
    ['GET', '/api/douyin/session'],
    ['GET', '/api/temu/products?page=1&pageSize=5'],
    ['GET', '/api/douyin/products?page=1&pageSize=5'],
    ['GET', '/api/platform-accounts/stores?platform=douyin'],
    ['GET', '/api/platform-accounts/stores?platform=temu'],
  ]
  for (const [method, p] of probes) {
    const { res, body } = await jfetch(`${BASE}${p}`, { method, headers: auth })
    const ok = res.status < 500
    record(`api ${method} ${p}`, ok, `HTTP ${res.status} ${redact(JSON.stringify(body)).slice(0, 160)}`)
  }

  printSummary()
  const failed = results.filter((r) => !r.ok)
  process.exit(failed.length ? 1 : 0)
}

function printSummary() {
  console.log('\n=== SUMMARY ===')
  for (const r of results) {
    console.log(`${r.ok ? 'OK' : 'NG'} | ${r.step} | ${r.detail}`)
  }
  const failed = results.filter((x) => !x.ok).length
  console.log(`total=${results.length} fail=${failed}`)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
