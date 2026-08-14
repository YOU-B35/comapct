const DEFAULT_PORT = 18765
const DEFAULT_PANEL_PORT = 18766
const INSTALL_HINT_KEY = 'crosshub_helper_installed'

function isLocalDevHost(hostname = typeof window !== 'undefined' ? window.location.hostname : '') {
  const host = String(hostname || '').toLowerCase()
  return host === 'localhost' || host === '127.0.0.1' || host === '[::1]'
}

/**
 * 探测本机 CrossHub 同步助手健康端口（默认 :18765）。
 * true 仅表示本机有进程，不代表当前租户 Java 心跳在线。
 */
export async function probeLocalAgent(port = DEFAULT_PORT, timeoutMs = 2500) {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    await fetch(`http://127.0.0.1:${port}/health`, {
      method: 'GET',
      mode: 'no-cors',
      signal: controller.signal,
    })
    return true
  } catch {
    return false
  } finally {
    window.clearTimeout(timer)
  }
}

/**
 * 本地 Vite 开发时：若助手误连线上，调用面板热切换到 :18080。
 * 生产域名不会触发。
 */
export async function alignLocalDevHelperJava(timeoutMs = 2500) {
  if (!isLocalDevHost()) {
    return { attempted: false, ok: false, live_java_api_url: '' }
  }
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`http://127.0.0.1:${DEFAULT_PANEL_PORT}/api/dev/use-local-java`, {
      method: 'POST',
      mode: 'cors',
      signal: controller.signal,
      cache: 'no-store',
    })
    const data = await res.json().catch(() => ({}))
    const live = String(data.live_java_api_url || data.java_api_url || '')
    const ok = Boolean(res.ok && data.ok && /127\.0\.0\.1:18080|localhost:18080/i.test(live))
    return { attempted: true, ok, live_java_api_url: live, message: data.msg || '' }
  } catch {
    return { attempted: true, ok: false, live_java_api_url: '' }
  } finally {
    window.clearTimeout(timer)
  }
}

/**
 * 读取本机助手面板绑定状态（:18766 /api/bind）。
 * 用于区分「助手未安装」与「助手已运行但未对应当前租户」。
 */
export async function fetchLocalHelperBind(timeoutMs = 2500) {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`http://127.0.0.1:${DEFAULT_PANEL_PORT}/api/bind`, {
      method: 'GET',
      mode: 'cors',
      signal: controller.signal,
      cache: 'no-store',
    })
    if (!res.ok) {
      return {
        reachable: true,
        bound: false,
        user_id: null,
        tenant_id: null,
        bound_account: '',
        java_api_url: '',
        live_java_api_url: '',
      }
    }
    const data = await res.json().catch(() => ({}))
    const live = String(data.live_java_api_url || data.java_api_url || '').trim()
    return {
      reachable: true,
      bound: Boolean(data.bound),
      user_id: data.user_id != null ? Number(data.user_id) : null,
      tenant_id: data.tenant_id != null ? Number(data.tenant_id) : null,
      bound_account: String(data.bound_account || '').trim(),
      java_api_url: String(data.java_api_url || '').trim(),
      live_java_api_url: live,
    }
  } catch {
    const processUp = await probeLocalAgent(DEFAULT_PORT, Math.min(timeoutMs, 1200))
    return {
      reachable: processUp,
      bound: false,
      user_id: null,
      tenant_id: null,
      bound_account: '',
      java_api_url: '',
      live_java_api_url: '',
    }
  } finally {
    window.clearTimeout(timer)
  }
}

/** localhost 页面却连线上助手（或反过来）时返回提示文案，否则空串 */
export function helperApiMismatchHint(
  javaApiUrl,
  pageHostname = typeof window !== 'undefined' ? window.location.hostname : '',
) {
  const api = String(javaApiUrl || '')
  const localPage = pageHostname === 'localhost' || pageHostname === '127.0.0.1'
  const helperOnline = /yoto\.work/i.test(api)
  const helperLocal = /127\.0\.0\.1:18080|localhost:18080/i.test(api)
  if (localPage && helperOnline) {
    return '本机页面连的是本地 Java，但 Sync Helper 仍指向线上。请重新执行 scripts\\start-local.ps1（会自动校正助手），或运行 scripts\\ensure-local-helper.ps1'
  }
  if (!localPage && helperLocal) {
    return '当前是线上站点，但本机助手指向 localhost:18080。请清除助手绑定后用线上绑定码重新绑定，或去掉 config 中的 allow_local_java'
  }
  return ''
}

export async function fetchLocalInstallInfo(timeoutMs = 2000) {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`http://127.0.0.1:${DEFAULT_PANEL_PORT}/api/install-info`, {
      method: 'GET',
      mode: 'cors',
      signal: controller.signal,
      cache: 'no-store',
    })
    if (!res.ok) {
      return { reachable: true, installed: false }
    }
    const data = await res.json().catch(() => ({}))
    return {
      reachable: true,
      installed: Boolean(data.installed),
      version: String(data.version || ''),
    }
  } catch {
    return { reachable: false, installed: false, version: '' }
  } finally {
    window.clearTimeout(timer)
  }
}

export async function probeHelperInstallState() {
  const [bind, install, health] = await Promise.all([
    fetchLocalHelperBind(),
    fetchLocalInstallInfo(),
    probeLocalAgent(),
  ])
  return {
    processUp: Boolean(health || bind.reachable),
    installed: Boolean(install.installed || bind.reachable || hasLocalHelperInstallHint()),
    localTenantId: bind.tenant_id,
    localBound: bind.bound,
  }
}

export function getHelperPanelUrl() {
  return `http://127.0.0.1:${DEFAULT_PANEL_PORT}/`
}

/**
 * 本机面板直连打开 Temu 登录（绕过 Java 任务队列，秒开浏览器）。
 * 面板不可达或失败时返回 null，由调用方回退到 /api/temu/login/enqueue。
 */
export async function openLocalTemuLogin(
  { tenantId, sessionKey, platformAccountId, account } = {},
  timeoutMs = 4000,
) {
  let tid = Number(tenantId)
  if (!Number.isFinite(tid) || tid <= 0) {
    try {
      const bind = await fetchLocalHelperBind(Math.min(timeoutMs, 1500))
      tid = Number(bind?.tenant_id)
    } catch {
      tid = NaN
    }
  }
  if (!Number.isFinite(tid) || tid <= 0) return null
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const body = {
      tenant_id: tid,
      platform: 'temu',
    }
    if (sessionKey) body.session_key = String(sessionKey)
    if (platformAccountId) body.platform_account_id = String(platformAccountId)
    if (account) body.account = String(account)
    const res = await fetch(`http://127.0.0.1:${DEFAULT_PANEL_PORT}/api/login`, {
      method: 'POST',
      mode: 'cors',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
      cache: 'no-store',
    })
    if (!res.ok) return null
    const data = await res.json().catch(() => ({}))
    if (!data?.ok) return null
    return {
      queued: true,
      mode: 'local_panel',
      tenant_id: tid,
      session_key: sessionKey || '',
      message: data.msg || '正在打开登录窗口...',
    }
  } catch {
    return null
  } finally {
    window.clearTimeout(timer)
  }
}

export function markHelperInstalledLocally() {
  try {
    localStorage.setItem(INSTALL_HINT_KEY, '1')
  } catch {
    /* ignore */
  }
}

export function hasLocalHelperInstallHint() {
  try {
    return localStorage.getItem(INSTALL_HINT_KEY) === '1'
  } catch {
    return false
  }
}

export function getAgentProbePort() {
  return DEFAULT_PORT
}
