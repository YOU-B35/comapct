import { service } from './request'

export async function list1688MonitorTargets() {
  const res = await service.get('/api/monitor/targets', { params: { platform: '1688' } })
  return res?.data ?? res
}

export async function create1688MonitorTarget(payload) {
  const res = await service.post('/api/monitor/targets', payload)
  return res?.data ?? res
}

export async function update1688MonitorTarget(id, payload) {
  const res = await service.put(`/api/monitor/targets/${id}`, payload)
  return res?.data ?? res
}

export async function delete1688MonitorTarget(id) {
  const res = await service.delete(`/api/monitor/targets/${id}`)
  return res?.data ?? res
}

export async function update1688MonitorSchedule(targetId, payload) {
  const res = await service.put(`/api/monitor/targets/${targetId}/schedule`, payload)
  return res?.data ?? res
}

export async function trigger1688MonitorTarget(targetId, payload = {}) {
  const res = await service.post(`/api/monitor/targets/${targetId}/trigger`, payload)
  return res?.data ?? res
}

export async function fetch1688MonitorLatest(targetId) {
  const res = await service.get(`/api/monitor/targets/${targetId}/latest`)
  return res?.data ?? res
}

export async function fetch1688MonitorTrend(targetId, { days = 30, productId = '' } = {}) {
  const params = { days }
  if (productId) params.product_id = productId
  const res = await service.get(`/api/monitor/targets/${targetId}/trend`, { params })
  return res?.data ?? res
}

export async function fetch1688MonitorSignals(targetId, limit = 50) {
  const res = await service.get(`/api/monitor/targets/${targetId}/signals`, { params: { limit } })
  return res?.data ?? res
}

export async function fetch1688MonitorJob(jobId) {
  const res = await service.get(`/api/monitor/jobs/${jobId}`, { skipGlobalErrorToast: true })
  return res?.data ?? res
}

export async function fetch1688MonitorJobs(targetId, limit = 20) {
  const res = await service.get('/api/monitor/jobs', {
    params: { target_id: targetId, limit },
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res
}
