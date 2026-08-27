import { probeLocalAgent, alignLocalDevHelperJava } from './agentProbe.js'

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
  // 默认不自动打开面板（避免误弹「桌面工作台」UI）；确需自动打开时传 openPanel。
  const openPanel = options.openPanel || null
  const sleep = options.sleep || defaultSleep
  const alignLocal = options.alignLocal || (() => alignLocalDevHelperJava())

  if (await probe()) {
    try {
      await alignLocal()
    } catch {
      /* ignore */
    }
    if (openPanel) openPanel()
    return { status: 'already_running', message: '本机助手已在运行' }
  }

  trigger(HELPER_PROTOCOL_START)

  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    await sleep(pollMs)
    if (await probe()) {
      try {
        await alignLocal()
      } catch {
        /* ignore */
      }
      if (openPanel) openPanel()
      return { status: 'started', message: '助手已启动' }
    }
  }

  return {
    status: 'not_found',
    message:
      '未检测到本机助手。请先解压安装包并双击 SETUP.cmd（或 CrossHub-Sync-Helper.exe）启动；若浏览器弹出打开提示请点允许。启动后再点「连接助手」。',
  }
}
