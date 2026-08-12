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
import { enrichAllProducts, normalizeSalesLast7Days } from '@/utils/temu'
import { hasBackendSession } from './backendSession'
import { isTemuBackendEnabled, TEMU_API_BASE_URL } from './config'
import {
  fetchAliexpressDemoData,
} from './aliexpressDemoLocal'
import {
  fetchCachedAliExpressOrders,
  syncTodayAliExpressOrders,
} from './aliexpressOrdersLocal'
import {
  confirmViolationAppeal,
  fetchAliExpressViolations as loadStoredViolations,
  syncAliExpressViolations,
} from './aliexpressViolationsLocal'

const CRAWL_POLL_MS = 2000
const CRAWL_MAX_WAIT_MS = 300000

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function canUseAliExpressBackend(auth) {
  return hasBackendSession(auth)
}

/** AE seller session probe (HelperStatusBar). No real AE session API yet — stay honest/offline. */
export async function fetchAliExpressSessionStatus() {
  return { ready: false, requires_auth: true, agent_online: false }
}

export async function openAliExpressSellerLogin() {
  throw new AppApiError(
    'AliExpress 卖家登录暂未接入，请通过本机 Sync Helper 完成登录',
    'NOT_IMPLEMENTED',
  )
}

export async function pollAliExpressSessionUntilReady() {
  return fetchAliExpressSessionStatus()
}


export function formatAliExpressCrawlError(errorCode, message) {
  return getAppErrorMessage(errorCode, message || '数据同步失败')
}

export async function triggerAliExpressCrawl(options = {}) {
  const crawlOpts = normalizeCrawlOptions(options)
  assertPlatformCrawlAllowed(null, crawlOpts)

  const body = { scope: options.scope || 'all' }
  if (options.reportTime) body.report_time = options.reportTime
  applyCrawlRequestFlags(body, options)

  const token = getAccessToken()
  const res = await axios.post('/api/aliexpress/crawl', body, {
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
  throwIfCrawlCooldownResponse(res, payload, '触发 AliExpress 爬取失败')
  if (res.status === 202 || payload?.code === 0) {
    return { conflict: false, job }
  }
  if (res.status === 409 || payload?.code === 409) {
    return {
      conflict: true,
      job,
      message: getAppErrorMessage(payload?.error_code, payload?.msg || '已有爬取任务进行中'),
    }
  }
  throw toAppApiError(payload, '触发爬取失败')
}

export async function fetchAliExpressCrawlJob(jobId) {
  const res = await service.get(`/api/aliexpress/crawl/${jobId}`, { skipGlobalErrorToast: true })
  return res?.data ?? res
}

export async function fetchAliExpressSyncJobs({ limit = 20 } = {}) {
  const res = await service.get('/api/aliexpress/jobs', { params: { limit }, skipGlobalErrorToast: true })
  const body = res?.data || res || {}
  return Array.isArray(body.jobs) ? body.jobs : []
}

export async function refreshAliExpressDataWithCrawl(options = {}) {
  const crawlOpts = normalizeCrawlOptions(options)

  const started = await triggerAliExpressCrawl(options)
  const jobId = started.job?.job_id || started.job?.jobId || started.job?.id
  if (!jobId) {
    if (started.conflict) {
      throw new AppApiError(
        started.message || '已有爬取任务进行中，请稍后再试',
        'CRAWL_IN_PROGRESS',
      )
    }
    throw new AppApiError('未获取到爬取任务 ID', 'CRAWL_PROCESS_FAILED')
  }

  const deadline = Date.now() + CRAWL_MAX_WAIT_MS
  while (Date.now() < deadline) {
    const job = await fetchAliExpressCrawlJob(jobId)
    if (job.status === 'success' || job.status === 'partial') {
      const result = {
        success: true,
        partial: job.status === 'partial',
        job,
        conflict: started.conflict,
        message: job.status === 'partial'
          ? (job.error_message || '爬取已完成，但任务收尾异常，页面数据可能已更新')
          : (started.conflict ? '已等待进行中的爬取任务完成' : ''),
      }
      markPlatformCrawlOnSuccess(null, result, { enabled: crawlOpts.recordCooldown })
      return result
    }
    if (job.status === 'failed') {
      throw new AppApiError(
        formatAliExpressCrawlError(job.error_code, job.error_message),
        job.error_code || 'CRAWL_PROCESS_FAILED',
      )
    }
    await sleep(CRAWL_POLL_MS)
  }
  throw new AppApiError(
    started.conflict ? '已有爬取任务进行中，等待超时，请稍后再试' : '数据同步超时，请稍后重试',
    started.conflict ? 'CRAWL_IN_PROGRESS' : 'CRAWL_TIMEOUT',
  )
}

async function triggerViolationSyncCrawl(options = {}) {
  const crawlOpts = normalizeCrawlOptions(options)
  assertPlatformCrawlAllowed(null, crawlOpts)

  const body = {}
  applyCrawlRequestFlags(body, options)
  const token = getAccessToken()
  const res = await axios.post('/api/aliexpress/violations/sync', body, {
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
  throwIfCrawlCooldownResponse(res, payload, '触发违规同步失败')
  if (res.status === 202 || payload?.code === 0) {
    return job
  }
  throw toAppApiError(payload, '触发违规同步失败')
}

async function waitForCrawlJob(jobId) {
  const deadline = Date.now() + CRAWL_MAX_WAIT_MS
  while (Date.now() < deadline) {
    const job = await fetchAliExpressCrawlJob(jobId)
    if (job.status === 'success') return job
    if (job.status === 'failed') {
      throw new AppApiError(
        formatAliExpressCrawlError(job.error_code, job.error_message),
        job.error_code || 'CRAWL_PROCESS_FAILED',
      )
    }
    await sleep(CRAWL_POLL_MS)
  }
  throw new AppApiError('违规同步超时，请稍后重试', 'CRAWL_TIMEOUT')
}

function unwrap(res) {
  return res?.data ?? res
}

export async function fetchAliExpressOperationalData({ storeId } = {}) {
  const params = {}
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/aliexpress/operational', { params })
  const body = unwrap(res)
  const products = enrichAllProducts((body.products || []).map((row) => ({
    ...row,
    storeId: row.storeId || row.store_id,
    name: row.name || row.productName,
    sellingPrice: row.sellingPrice ?? row.selling_price,
    costPrice: row.costPrice ?? row.cost_price,
    platformFeeRate: row.platformFeeRate ?? row.platform_fee_rate,
    logisticsFee: row.logisticsFee ?? row.logistics_fee,
    officialStock: row.officialStock ?? row.official_stock,
    localStock: row.localStock ?? row.local_stock,
    daysWithoutSale: row.daysWithoutSale ?? row.days_without_sale,
    dailySales: row.dailySales ?? row.daily_sales,
    salesLast7Days: normalizeSalesLast7Days(row.salesLast7Days ?? row.sales_last7_days),
    owner: row.owner || '',
  })))
  return {
    products,
    broadcasts: body.broadcasts || [],
    meta: {
      source: 'backend',
      reportDay: body.report_day,
    },
  }
}

export async function fetchTodayAliExpressOrdersFromApi({ storeId, refresh = false, ...crawlOptions } = {}) {
  const params = {}
  if (storeId && storeId !== 'all') params.store_id = storeId

  async function loadCachedOrders() {
    const res = await service.get('/api/aliexpress/orders/today', { params, skipGlobalErrorToast: true })
    const body = unwrap(res)
    return {
      orders: body.orders || [],
      syncedAt: body.syncedAt || body.synced_at || '',
      date: body.date || '',
    }
  }

  if (refresh) {
    try {
      await refreshAliExpressDataWithCrawl(crawlOptions)
    } catch (err) {
      const cached = await loadCachedOrders()
      if ((cached.orders || []).length) {
        return {
          ...cached,
          message: `${err.message || '实时同步失败'}，已展示最近一次入库数据`,
        }
      }
      throw err
    }
  }
  return loadCachedOrders()
}

export async function loadAliExpressViolationsFromApi({ storeId } = {}) {
  const params = {}
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/aliexpress/violations', { params })
  const body = unwrap(res)
  return {
    violations: body.violations || [],
    syncedAt: body.syncedAt || body.synced_at || '',
  }
}

export async function crawlAliExpressViolationsFromApi(options = {}) {
  const crawlOpts = normalizeCrawlOptions(options)

  const job = await triggerViolationSyncCrawl(options)
  const jobId = job?.job_id
  if (!jobId) {
    throw new AppApiError('未获取到违规同步任务 ID', 'CRAWL_PROCESS_FAILED')
  }
  await waitForCrawlJob(jobId)
  const data = await loadAliExpressViolationsFromApi()
  markPlatformCrawlOnSuccess(null, { success: true }, { enabled: crawlOpts.recordCooldown })
  return data
}

export async function confirmAliExpressViolationAppealFromApi(id, payload) {
  const res = await service.patch(`/api/aliexpress/violations/${id}`, {
    appealStatus: payload.appealStatus,
    appealResult: payload.appealResult,
  })
  return unwrap(res)
}

export async function loadAliExpressModuleData({ auth, storeId, stores }) {
  if (!canUseAliExpressBackend(auth)) {
    const demoRes = fetchAliexpressDemoData(stores)
    return {
      products: demoRes.data.products,
      broadcasts: demoRes.data.broadcasts,
      source: 'demo',
    }
  }
  const data = await fetchAliExpressOperationalData({ storeId })
  return {
    products: data.products,
    broadcasts: data.broadcasts,
    source: 'backend',
    meta: data.meta,
  }
}

export {
  fetchAliexpressDemoData,
  fetchCachedAliExpressOrders,
  syncTodayAliExpressOrders,
  loadStoredViolations,
  syncAliExpressViolations,
  confirmViolationAppeal,
}
