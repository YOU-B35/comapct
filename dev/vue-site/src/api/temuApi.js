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
import { mapReptileSaleToTemuProduct } from '@/utils/mapReptileSaleToTemuProduct'
import { enrichAllProducts } from '@/utils/temu'
import { applyServerAlgorithms } from '@/utils/temuServerAlgo'
import { hasBackendSession } from './backendSession'
import { scopeStores } from '@/utils/scope'
import { isTemuBackendEnabled, TEMU_API_BASE_URL } from './config'
import { fetchPlatformStores } from './platformAccounts'
import {
  fetchLocalTemuSalesTrend,
  fetchLocalTemuStores,
  loadLocalTemuOperationalData,
} from './temuDemoLocal'

const TEMU_PLATFORM = 'temu'

function isDemoShopId(id) {
  return /^(demo_|mock_)/i.test(String(id || ''))
}

export function canUseTemuBackend(auth) {
  return hasBackendSession(auth)
}

export async function fetchTemuSessionStatus() {
  const res = await service.get('/api/temu/session', { skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

export async function fetchTemuIntegrationStatus() {
  const res = await service.get('/api/temu/integration/status', { skipGlobalErrorToast: true })
  return { success: true, data: res?.data ?? res ?? {} }
}

export async function openTemuSellerLogin(payload = {}) {
  const body = {}
  if (payload.platformAccountId) {
    body.platform_account_id = payload.platformAccountId
  }
  const res = await service.post('/api/temu/login/open', body, { skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

/** Open real Chrome for Temu buyer-side / competitor frontend login. */
export async function openTemuFrontendLogin(payload = {}) {
  const res = await service.post(
    '/api/temu/frontend-login/open',
    { url: payload.url || undefined },
    { skipGlobalErrorToast: true },
  )
  return res?.data ?? res ?? {}
}

/**
 * 轮询 session 直至 ready。
 * TM-P3：退避 2s→5s，默认最多约 20 次，避免打爆 probe；可用 timeoutMs/maxAttempts 覆盖。
 */
export async function pollTemuSessionUntilReady({
  timeoutMs = 90000,
  intervalMs = 2000,
  maxIntervalMs = 5000,
  maxAttempts = 20,
  signal = null,
} = {}) {
  const deadline = Date.now() + Math.max(1000, timeoutMs)
  let delay = Math.max(500, intervalMs)
  let attempt = 0

  while (attempt < maxAttempts && Date.now() < deadline) {
    if (signal?.aborted) {
      throw new AppApiError('已取消登录等待', 'CRAWL_INTERRUPTED')
    }
    const session = await fetchTemuSessionStatus()
    if (session.ready) return session
    if (session.profile_busy && session.logged_in && session.mall_id) return session

    attempt += 1
    if (attempt >= maxAttempts || Date.now() >= deadline) break
    const waitMs = Math.min(delay, Math.max(0, deadline - Date.now()))
    if (waitMs <= 0) break
    await sleep(waitMs)
    delay = Math.min(maxIntervalMs, Math.round(delay * 1.4))
  }

  const last = await fetchTemuSessionStatus()
  if (last.ready) return last
  if (last.profile_busy && last.logged_in && last.mall_id) return last
  throw new AppApiError('登录等待超时，请确认已在弹出窗口完成登录并选择店铺后重试', 'CRAWL_NOT_LOGGED_IN')
}

export async function pollTemuProfileIdle({
  timeoutMs = 120000,
  intervalMs = 2000,
  maxIntervalMs = 5000,
  maxAttempts = 30,
  signal = null,
} = {}) {
  const deadline = Date.now() + Math.max(1000, timeoutMs)
  let delay = Math.max(500, intervalMs)
  let attempt = 0

  while (attempt < maxAttempts && Date.now() < deadline) {
    if (signal?.aborted) {
      throw new AppApiError('已取消等待', 'CRAWL_INTERRUPTED')
    }
    const session = await fetchTemuSessionStatus()
    if (!session.profile_busy) return session

    attempt += 1
    if (attempt >= maxAttempts || Date.now() >= deadline) break
    const waitMs = Math.min(delay, Math.max(0, deadline - Date.now()))
    if (waitMs <= 0) break
    await sleep(waitMs)
    delay = Math.min(maxIntervalMs, Math.round(delay * 1.4))
  }

  const last = await fetchTemuSessionStatus()
  if (!last.profile_busy) return last
  throw new AppApiError(
    '登录窗口仍占用浏览器，请关闭 CrossHub 弹出的登录浏览器后重试',
    'CRAWL_IN_PROGRESS',
  )
}

export async function fetchTemuStores(auth) {
  if (canUseTemuBackend(auth)) {
    const [shopsRes, boundRes] = await Promise.all([
      service.get('/api/temu/shops', { skipGlobalErrorToast: true }),
      fetchPlatformStores(TEMU_PLATFORM),
    ])
    const list = shopsRes?.data ?? []
    const crawledShops = (Array.isArray(list) ? list : [])
      .filter((shop) => !isDemoShopId(shop.shop_id))
      .map((shop) => ({
        id: shop.shop_id,
        storeName: shop.shop_name || shop.bound_store_name || shop.shop_id,
        platform: TEMU_PLATFORM,
        isUpload: shop.is_upload,
        externalShopId: shop.external_shop_id || shop.shop_id,
        platformAccountId: shop.platform_account_id || '',
      }))

    const boundStores = (boundRes?.data || boundRes || []).map((store) => ({
      ...store,
      externalShopId: store.externalShopId || store.external_shop_id || '',
    }))
    const boundByExt = new Map()
    for (const store of boundStores) {
      const extId = String(store.externalShopId || '').trim()
      if (extId) boundByExt.set(extId, store)
    }

    const merged = []
    const seen = new Set()

    // 以爬虫入库的店铺为准（同一 Temu 账号可有多家 mall）
    for (const shop of crawledShops) {
      const id = String(shop.id || '').trim()
      if (!id || seen.has(id)) continue
      seen.add(id)
      const bound = boundByExt.get(id)
      merged.push({
        id,
        storeName: shop.storeName,
        platform: TEMU_PLATFORM,
        isUpload: shop.isUpload,
        externalShopId: shop.externalShopId || id,
        accountId: bound?.id || shop.platformAccountId || '',
        needsShopLink: !bound,
      })
    }

    // 已绑定但尚未爬到数据的店铺仍保留入口（必须有 externalShopId 才能查后端）
    for (const store of boundStores) {
      const extId = String(store.externalShopId || '').trim()
      if (!extId) continue
      const id = extId
      if (seen.has(id) || isDemoShopId(id)) continue
      seen.add(id)
      merged.push({
        id,
        storeName: store.storeName || id,
        platform: TEMU_PLATFORM,
        isUpload: undefined,
        externalShopId: extId || id,
        accountId: store.id,
        needsShopLink: !extId,
      })
    }

    return scopeStores(merged, auth)
  }
  return fetchLocalTemuStores(auth)
}

export async function fetchTemuOperationalData({ shopId } = {}) {
  const params = {}
  if (shopId && shopId !== 'all') params.shop_id = shopId

  const res = await service.get('/api/temu/operational', { params })
  const products = (res.products || []).map((row) => mapReptileSaleToTemuProduct(row))
  const enriched = enrichAllProducts(products)
  const merged = applyServerAlgorithms(enriched, {
    loseProducts: res.lose_products || [],
    lowWarnings: res.low_warnings || [],
    inventoryWarnings: res.inventory_warnings || [],
    overloadProducts: res.overload_products || [],
  })

  return {
    products: merged,
    meta: {
      source: 'backend',
      reportTime: res.report_time,
      salesCount: products.length,
      loseCount: (res.lose_products || []).length,
      restockCount: (res.inventory_warnings || []).length,
      overloadCount: (res.overload_products || []).length,
    },
  }
}

export async function fetchTemuSalesTrend({ auth, shopId, days = 7 } = {}) {
  if (canUseTemuBackend(auth)) {
    const params = { days }
    if (shopId && shopId !== 'all') params.shop_id = shopId
    const res = await service.get('/api/temu/trend', { params })
    return {
      labels: res.labels || [],
      values: res.values || [],
      estimated: res.estimated || [],
    }
  }
  return fetchLocalTemuSalesTrend({ shopId, days })
}

export async function loadTemuModuleData({ auth, shopId }) {
  if (canUseTemuBackend(auth)) {
    return fetchTemuOperationalData({ shopId })
  }
  return loadLocalTemuOperationalData({ shopId })
}

const CRAWL_POLL_MS = 2000
const CRAWL_MAX_WAIT_MS = 300000

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function formatCrawlError(errorCode, message) {
  return getAppErrorMessage(errorCode, message || '数据同步失败')
}

export async function triggerTemuCrawl(options = {}) {
  const crawlOpts = normalizeCrawlOptions(options)
  assertPlatformCrawlAllowed(null, crawlOpts)

  const body = {}
  if (options.reportTime) body.report_time = options.reportTime
  applyCrawlRequestFlags(body, options)

  const token = getAccessToken()
  const res = await axios.post('/api/temu/crawl', body, {
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
  throwIfCrawlCooldownResponse(res, payload, '触发 Temu 爬取失败')
  if (res.status === 202 || payload?.code === 0) {
    return { conflict: false, job }
  }
  if (res.status === 409 || payload?.code === 409) {
    return {
      conflict: true,
      job: job?.job_id || job?.jobId ? job : (payload?.data ?? job),
      message: getAppErrorMessage(payload?.error_code, payload?.msg || job?.message || '已有爬取任务进行中'),
    }
  }
  throw toAppApiError(payload, '触发爬取失败')
}

export async function fetchTemuCrawlJob(jobId) {
  const res = await service.get(`/api/temu/crawl/${jobId}`, { skipGlobalErrorToast: true })
  return res?.data ?? res
}

/** 全平台日批计划 + 各平台最近同步结果/错误（打开应用时展示） */
export async function fetchPlatformSyncStatus() {
  const res = await service.get('/api/platform/sync-status', { skipGlobalErrorToast: true })
  return res?.data ?? res
}

/** @deprecated 使用 fetchPlatformSyncStatus；兼容旧调用 */
export async function fetchTemuSyncStatus() {
  return fetchPlatformSyncStatus()
}

export async function refreshTemuDataWithCrawl(options = {}) {
  const crawlOpts = normalizeCrawlOptions(options)

  const started = await triggerTemuCrawl(options)
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
    const job = await fetchTemuCrawlJob(jobId)
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
        formatCrawlError(job.error_code, job.error_message),
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
