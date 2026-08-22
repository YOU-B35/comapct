import { service } from './request'

export async function listPddMonitorTargets() {
  const res = await service.get('/api/monitor/targets', { params: { platform: 'pdd' } })
  return res?.data ?? res
}

export async function createPddMonitorTarget(payload) {
  const res = await service.post('/api/monitor/targets', payload)
  return res?.data ?? res
}

export async function updatePddMonitorTarget(id, payload) {
  const res = await service.put(`/api/monitor/targets/${id}`, payload)
  return res?.data ?? res
}

export async function deletePddMonitorTarget(id) {
  const res = await service.delete(`/api/monitor/targets/${id}`)
  return res?.data ?? res
}

export async function updatePddMonitorSchedule(targetId, payload) {
  const res = await service.put(`/api/monitor/targets/${targetId}/schedule`, payload)
  return res?.data ?? res
}

export async function triggerPddMonitorTarget(targetId, payload = {}) {
  const res = await service.post(`/api/monitor/targets/${targetId}/trigger`, payload)
  return res?.data ?? res
}

export async function fetchPddMonitorLatest(targetId) {
  const res = await service.get(`/api/monitor/targets/${targetId}/latest`)
  return res?.data ?? res
}

export async function fetchPddMonitorTrend(targetId, { days = 30, productId = '' } = {}) {
  const params = { days }
  if (productId) params.product_id = productId
  const res = await service.get(`/api/monitor/targets/${targetId}/trend`, { params })
  return res?.data ?? res
}

export async function fetchPddMonitorSignals(targetId, limit = 50) {
  const res = await service.get(`/api/monitor/targets/${targetId}/signals`, { params: { limit } })
  return res?.data ?? res
}

export async function fetchPddMonitorJob(jobId) {
  const res = await service.get(`/api/monitor/jobs/${jobId}`, { skipGlobalErrorToast: true })
  return res?.data ?? res
}
