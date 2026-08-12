import { probeLocalAgent, getHelperPanelUrl } from './agentProbe.js'

export const HELPER_PROTOCOL_START = 'crosshub-sync-helper://start'

export function triggerHelperProtocol(url = HELPER_PROTOCOL_START) {
  try {
    const iframe = document.createElement('iframe')
    iframe.style.display = 'none'
    iframe.src = url
    document.body.appendChild(iframe)
    setTimeout(() => iframe.remove(), 4000)
  } catch {
    /* ignore */
  }
  try {
    const link = document.createElement('a')
    link.href = url
    document.body.appendChild(link)
    link.click()
    link.remove()
  } catch {
    /* ignore */
  }
}

function defaultSleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * @returns {Promise<{ status: 'already_running'|'started'|'not_found', message: string }>}
 */
export async function connectLocalHelper(options = {}) {
  const timeoutMs = Number(options.timeoutMs) > 0 ? Number(options.timeoutMs) : 20000
  const pollMs = Number(options.pollMs) > 0 ? Number(options.pollMs) : 1000
  const probe = options.probe || (() => probeLocalAgent())
  const trigger = options.trigger || triggerHelperProtocol
  const openPanel = options.openPanel || ((url) => window.open(url, '_blank', 'noopener'))
  const sleep = options.sleep || defaultSleep

  if (await probe()) {
    try {
      openPanel(getHelperPanelUrl())
    } catch {
      /* ignore */
    }
    return { status: 'already_running', message: '本机助手已在运行' }
  }

  trigger(HELPER_PROTOCOL_START)

  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    await sleep(pollMs)
    if (await probe()) {
      try {
        openPanel(getHelperPanelUrl())
      } catch {
        /* ignore */
      }
      return { status: 'started', message: '助手已启动' }
    }
  }

  return {
    status: 'not_found',
    message: '未检测到本机助手，请先下载安装 Sync Helper',
  }
}
