import axios from 'axios'
import { AppApiError, getAppErrorMessage, toAppApiError } from '@/utils/appErrorCode'
import {
  assertPlatformCrawlAllowed,
  applyCrawlRequestFlags,
  markPlatformCrawlOnSuccess,
  normalizeCrawlOptions,
  throwIfCrawlCooldownResponse,
} from '@/utils/platformSyncCooldown'
import { service, getAccessToken } from './request'
import { hasBackendSession } from './backendSession'
import { TEMU_API_BASE_URL } from './config'

const CRAWL_POLL_MS = 2000
const CRAWL_MAX_WAIT_MS = 300000

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function canUseAlibaba1688Backend(auth) {
  return hasBackendSession(auth)
}

export function formatAlibaba1688CrawlError(errorCode, message) {
  return getAppErrorMessage(errorCode, message || '1688 同步失败')
}

export async function triggerAlibaba1688Crawl(options = {}) {
  const crawlOpts = normalizeCrawlOptions(options)
  assertPlatformCrawlAllowed(null, crawlOpts)

  const body = {
    jobType: options.jobType || 'sync',
  }
  if (options.storeId) body.storeId = options.storeId
  applyCrawlRequestFlags(body, options)

  const token = getAccessToken()
  const res = await axios.post('/api/1688/crawl', body, {
    baseURL: import.meta.env.DEV ? '' : TEMU_API_BASE_URL,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    validateStatus: () => true,
    timeout: 120000,
  })

  const payload = res.data
  const job = payload?.data ?? payload
  throwIfCrawlCooldownResponse(res, payload, '触发 1688 同步失败')
  if (res.status === 202 || payload?.code === 0) {
    return { conflict: false, job }
  }
  if (res.status === 409 || payload?.code === 409) {
    return {
      conflict: true,
      job,
      message: getAppErrorMessage(payload?.error_code, payload?.msg || '已有同步任务进行中'),
    }
  }
  throw toAppApiError(payload, '触发 1688 同步失败')
}

export async function fetchAlibaba1688CrawlJob(jobId) {
  const res = await service.get(`/api/1688/crawl/${jobId}`, { skipGlobalErrorToast: true })
  return res?.data ?? res
}

export async function refreshAlibaba1688DataWithCrawl(options = {}) {
  const crawlOpts = normalizeCrawlOptions(options)
  const started = await triggerAlibaba1688Crawl(options)
  const jobId = started.job?.job_id || started.job?.jobId || started.job?.id
  if (!jobId) {
    if (started.conflict) {
      throw new AppApiError(
        started.message || '已有同步任务进行中，请稍后再试',
        'CRAWL_IN_PROGRESS',
      )
    }
    throw new AppApiError('未获取到同步任务 ID', 'CRAWL_PROCESS_FAILED')
  }

  const deadline = Date.now() + CRAWL_MAX_WAIT_MS
  while (Date.now() < deadline) {
    const job = await fetchAlibaba1688CrawlJob(jobId)
    const status = job?.status
    if (status === 'success' || status === 'partial') {
      const result = { success: true, partial: status === 'partial', job, conflict: started.conflict }
      markPlatformCrawlOnSuccess(null, result, { enabled: crawlOpts.recordCooldown })
      return result
    }
    if (status === 'need_login') {
      const err = new AppApiError(
        formatAlibaba1688CrawlError(job.errorCode || job.error_code, job.errorMessage || job.error_message || job.message),
        'CRAWL_1688_NOT_LOGGED_IN',
      )
      err.job = job
      throw err
    }
    if (status === 'failed') {
      const err = new AppApiError(
        formatAlibaba1688CrawlError(job.error_code || job.errorCode, job.error_message || job.errorMessage),
        job.error_code || job.errorCode || 'CRAWL_PROCESS_FAILED',
      )
      err.job = job
      throw err
    }
    await sleep(CRAWL_POLL_MS)
  }
  throw new AppApiError(
    started.conflict ? '已有同步任务进行中，等待超时' : '1688 同步超时',
    started.conflict ? 'CRAWL_IN_PROGRESS' : 'CRAWL_TIMEOUT',
  )
}

export async function fetchAlibaba1688Operational({ storeId } = {}) {
  const res = await service.get('/api/1688/operational', {
    params: storeId && storeId !== 'all' ? { storeId } : {},
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? {}
}

export async function fetchAlibaba1688Session() {
  const res = await service.get('/api/1688/session', { skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

export async function enqueueAlibaba1688Login() {
  const res = await service.post('/api/1688/login/open', {}, { skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

export async function enqueueAlibaba1688SessionProbe() {
  const res = await service.post('/api/1688/session/probe', {}, { skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

export async function enqueueAlibaba1688ProductsSync() {
  const res = await service.post('/api/1688/products/sync', {}, { skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

export async function fetchAlibaba1688Products({ tab = 'all', status = 'all', storeId } = {}) {
  const params = { tab, status }
  if (storeId && storeId !== 'all') params.storeId = storeId
  const res = await service.get('/api/1688/products', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

export async function enqueueAlibaba1688OrdersSync() {
  const res = await service.post('/api/1688/orders/sync', {}, { skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

export async function fetchAlibaba1688OrderSummary({ startDate, endDate, storeId } = {}) {
  const params = { startDate, endDate }
  if (storeId && storeId !== 'all') params.storeId = storeId
  const res = await service.get('/api/1688/operations/summary', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

export async function fetchAlibaba1688OrderTrend({ startDate, endDate, storeId } = {}) {
  const params = { startDate, endDate }
  if (storeId && storeId !== 'all') params.storeId = storeId
  const res = await service.get('/api/1688/operations/trend', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

export async function fetchAlibaba1688Orders({
  startDate,
  endDate,
  status = '',
  keyword = '',
  storeId,
  page = 1,
  pageSize = 20,
} = {}) {
  const params = { status, keyword, page, pageSize }
  if (startDate && endDate) {
    params.startDate = startDate
    params.endDate = endDate
  }
  if (storeId && storeId !== 'all') params.storeId = storeId
  const res = await service.get('/api/1688/orders', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

export async function fetchAlibaba1688ProductAnalytics({ type, storeId } = {}) {
  const params = { type }
  if (storeId && storeId !== 'all') params.storeId = storeId
  const res = await service.get('/api/1688/products/analytics', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

export async function fetchAlibaba1688SyncLogs({ limit = 20 } = {}) {
  const res = await service.get('/api/1688/sync-logs', {
    params: { limit },
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? {}
}

export async function fetchAlibaba1688PeerBestsellers({ page = 1, pageSize = 10 } = {}) {
  const res = await service.get('/api/1688/peer-bestsellers', {
    params: { page, pageSize },
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? {}
}

export async function enqueueAlibaba1688PeerBestsellersSync() {
  const res = await service.post('/api/1688/peer-bestsellers/sync', {}, { skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

/** Poll 1688 buyer session until ready (HelperStatusBar). */
export async function pollAlibaba1688SessionUntilReady({
  timeoutMs = 90000,
  intervalMs = 2000,
  maxIntervalMs = 5000,
  signal = null,
} = {}) {
  const deadline = Date.now() + Math.max(5000, timeoutMs)
  let delay = Math.max(800, intervalMs)
  try {
    await enqueueAlibaba1688SessionProbe()
  } catch {
    // ignore; still poll session
  }
  while (Date.now() < deadline) {
    if (signal?.aborted) {
      throw new DOMException('Aborted', 'AbortError')
    }
    const session = await fetchAlibaba1688Session()
    if (session?.ready || session?.logged_in) {
      return session
    }
    await new Promise((r) => setTimeout(r, delay))
    delay = Math.min(maxIntervalMs, Math.floor(delay * 1.25))
  }
  return fetchAlibaba1688Session()
}
