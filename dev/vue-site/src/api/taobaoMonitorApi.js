import { service } from './request'

export async function listTaobaoMonitorTargets() {
  const res = await service.get('/api/monitor/targets', { params: { platform: 'taobao' } })
  return res?.data ?? res
}

export async function createTaobaoMonitorTarget(payload) {
  const res = await service.post('/api/monitor/targets', payload)
  return res?.data ?? res
}

export async function updateTaobaoMonitorTarget(id, payload) {
  const res = await service.put(`/api/monitor/targets/${id}`, payload)
  return res?.data ?? res
}

export async function deleteTaobaoMonitorTarget(id) {
  const res = await service.delete(`/api/monitor/targets/${id}`)
  return res?.data ?? res
}

export async function updateTaobaoMonitorSchedule(targetId, payload) {
  const res = await service.put(`/api/monitor/targets/${targetId}/schedule`, payload)
  return res?.data ?? res
}

export async function triggerTaobaoMonitorTarget(targetId, payload = {}) {
  const res = await service.post(`/api/monitor/targets/${targetId}/trigger`, payload)
  return res?.data ?? res
}

export async function fetchTaobaoMonitorLatest(targetId) {
  const res = await service.get(`/api/monitor/targets/${targetId}/latest`)
  return res?.data ?? res
}

export async function fetchTaobaoMonitorTrend(targetId, { days = 30, productId = '' } = {}) {
  const params = { days }
  if (productId) params.product_id = productId
  const res = await service.get(`/api/monitor/targets/${targetId}/trend`, { params })
  return res?.data ?? res
}

export async function fetchTaobaoMonitorSignals(targetId, limit = 50) {
  const res = await service.get(`/api/monitor/targets/${targetId}/signals`, { params: { limit } })
  return res?.data ?? res
}

export async function fetchTaobaoMonitorJob(jobId) {
  const res = await service.get(`/api/monitor/jobs/${jobId}`, { skipGlobalErrorToast: true })
  return res?.data ?? res
}
