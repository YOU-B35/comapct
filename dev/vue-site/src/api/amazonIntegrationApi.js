import { service } from './request'

const POLL_MS = 2000
const MAX_WAIT_MS = 120000

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function unwrapData(res) {
  return res?.data ?? res
}

function mapCandidate(row) {
  if (!row) return row
  return {
    browserId: String(row.browser_id ?? row.browserId ?? ''),
    ziniaoStoreId: String(row.ziniao_store_id ?? row.ziniaoStoreId ?? row.store_id ?? row.storeId ?? ''),
    browserOauth: row.browser_oauth ?? row.browserOauth ?? '',
    browserName: row.browser_name ?? row.browserName ?? '',
    platformName: row.platform_name ?? row.platformName ?? '',
    storeUsername: row.store_username ?? row.storeUsername ?? '',
    browserIp: row.browser_ip ?? row.browserIp ?? '',
  }
}

export async function triggerZiniaoDiscover() {
  const res = await service.post('/api/amazon/ziniao/discover', {}, { skipGlobalErrorToast: true })
  return { success: true, data: unwrapData(res) }
}

export async function fetchZiniaoDiscoverJob(jobId) {
  const res = await service.get(`/api/amazon/ziniao/discover/${jobId}`, { skipGlobalErrorToast: true })
  return { success: true, data: unwrapData(res) }
}

export async function fetchZiniaoCandidates() {
  const res = await service.get('/api/amazon/ziniao/candidates', { skipGlobalErrorToast: true })
  const rows = unwrapData(res)
  return {
    success: true,
    data: (Array.isArray(rows) ? rows : []).map(mapCandidate),
  }
}

export async function bindZiniaoStores(stores) {
  const res = await service.post(
    '/api/amazon/ziniao/bind',
    {
      stores: (stores || []).map((item) => ({
        browser_id: item.browserId,
        ziniao_store_id: item.ziniaoStoreId,
        browser_oauth: item.browserOauth,
        browser_name: item.browserName,
        platform_name: item.platformName,
        store_username: item.storeUsername,
        browser_ip: item.browserIp,
      })),
    },
    { skipGlobalErrorToast: true },
  )
  return {
    success: true,
    message: res?.message || '绑定成功',
    data: unwrapData(res) || [],
  }
}

export async function discoverZiniaoStoresWithPoll() {
  const started = await triggerZiniaoDiscover()
  const jobId = started.data?.job_id || started.data?.task_id
  if (!jobId) {
    throw new Error('未返回发现任务 ID')
  }

  const deadline = Date.now() + MAX_WAIT_MS
  while (Date.now() < deadline) {
    await sleep(POLL_MS)
    const jobRes = await fetchZiniaoDiscoverJob(jobId)
    const job = jobRes.data || {}
    const status = String(job.status || '')
    if (status === 'success') {
      const stores = (job.stores || []).map(mapCandidate)
      return { jobId, status, stores }
    }
    if (status === 'failed') {
      throw new Error(job.error_message || job.error_code || '紫鸟店铺发现失败')
    }
  }
  throw new Error('紫鸟店铺发现超时，请确认 Agent 与紫鸟 CLI 或 WebDriver 已启动')
}
