const DEFAULT_PORT = 18765
const DEFAULT_PANEL_PORT = 18766
const INSTALL_HINT_KEY = 'crosshub_helper_installed'

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
      return { reachable: true, bound: false, user_id: null, tenant_id: null, bound_account: '' }
    }
    const data = await res.json().catch(() => ({}))
    return {
      reachable: true,
      bound: Boolean(data.bound),
      user_id: data.user_id != null ? Number(data.user_id) : null,
      tenant_id: data.tenant_id != null ? Number(data.tenant_id) : null,
      bound_account: String(data.bound_account || '').trim(),
    }
  } catch {
    const processUp = await probeLocalAgent(DEFAULT_PORT, Math.min(timeoutMs, 1200))
    return {
      reachable: processUp,
      bound: false,
      user_id: null,
      tenant_id: null,
      bound_account: '',
    }
  } finally {
    window.clearTimeout(timer)
  }
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
