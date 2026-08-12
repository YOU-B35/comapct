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

export function getHelperPanelUrl() {
  return `http://127.0.0.1:${DEFAULT_PANEL_PORT}/`
}

export function getAgentProbePort() {
  return DEFAULT_PORT
}
