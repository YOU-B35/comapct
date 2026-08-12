import { service } from './request'

function unwrapData(res) {
  return res?.data ?? res
}

export async function registerAgent(name) {
  const res = await service.post('/api/agent/register', { name }, { skipGlobalErrorToast: true })
  return {
    success: true,
    message: res?.message || 'Agent 注册成功',
    data: unwrapData(res),
  }
}

export async function setupLocalAgent(name = '本机助手') {
  const res = await service.post('/api/agent/setup', { name }, { skipGlobalErrorToast: true })
  return {
    success: true,
    message: res?.message || '同步助手已就绪',
    data: unwrapData(res),
  }
}

export async function fetchAgentNodes() {
  const res = await service.get('/api/agent/nodes', { skipGlobalErrorToast: true })
  const rows = unwrapData(res)
  return { success: true, data: Array.isArray(rows) ? rows : [] }
}

export async function fetchAmazonIntegrationStatus() {
  const res = await service.get('/api/amazon/integration/status', { skipGlobalErrorToast: true })
  return { success: true, data: unwrapData(res) || {} }
}
