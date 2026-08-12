const DEFAULT_PORT = 18765
const DEFAULT_PANEL_PORT = 18766

/**
 * 探测本机 CrossHub 同步助手健康端口（默认 :18765）。
 *
 * 注意：返回 true 仅表示「本机有进程」，不代表当前登录企业心跳在线。
 * 业务「是否可同步」必须以 Java 当前租户 agent_online 为准（见 utils/agentPresence.js）。
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
 * 读取本机助手面板绑定状态（:18766 /api/bind）。
 * 用于区分「助手未安装」与「助手已运行但绑定了其他 CrossHub 账号」。
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
      return { reachable: true, bound: false, user_id: null, tenant_id: null }
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

export function getHelperPanelUrl() {
  return `http://127.0.0.1:${DEFAULT_PANEL_PORT}/`
}

export function getAgentProbePort() {
  return DEFAULT_PORT
}
