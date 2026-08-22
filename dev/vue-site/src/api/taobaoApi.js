import { service } from './request'
import { hasBackendSession } from './backendSession'
import { AppApiError } from '@/utils/appErrorCode'

export function canUseTaobaoBackend(auth) {
  return hasBackendSession(auth)
}

export async function fetchTaobaoSession() {
  const res = await service.get('/api/taobao/session', { skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

export async function enqueueTaobaoLogin({ storeId } = {}) {
  const res = await service.post('/api/taobao/login/open', {}, {
    params: storeId && storeId !== 'all' ? { storeId } : {},
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? {}
}

export async function enqueueTaobaoSessionProbe({ storeId } = {}) {
  const res = await service.post('/api/taobao/session/probe', {}, {
    params: storeId && storeId !== 'all' ? { storeId } : {},
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? {}
}

/** Poll Taobao seller session until ready (HelperStatusBar). */
export async function pollTaobaoSessionUntilReady({
  timeoutMs = 90000,
  intervalMs = 2000,
  maxIntervalMs = 5000,
  signal = null,
  storeId = null,
} = {}) {
  const deadline = Date.now() + Math.max(5000, timeoutMs)
  let delay = Math.max(800, intervalMs)
  // Kick a probe once so agent writes fresh snapshot.
  try {
    await enqueueTaobaoSessionProbe({ storeId })
  } catch {
    // ignore; still poll session
  }
  while (Date.now() < deadline) {
    if (signal?.aborted) {
      throw new DOMException('Aborted', 'AbortError')
    }
    const session = await fetchTaobaoSession()
    if (session?.ready || session?.logged_in) {
      return session
    }
    await new Promise((r) => setTimeout(r, delay))
    delay = Math.min(maxIntervalMs, Math.floor(delay * 1.25))
  }
  return fetchTaobaoSession()
}

async function enqueueTaobaoSync({
  scope,
  force = true,
  storeId = null,
  dateWindow = null,
} = {}) {
  const body = { scope: scope || 'orders', force: !!force }
  if (storeId) body.store_id = storeId
  if (dateWindow) body.date_window = dateWindow
  try {
    const res = await service.post('/api/taobao/sync', body, { skipGlobalErrorToast: true })
    return res?.data ?? res ?? {}
  } catch (err) {
    const data = err?.response?.data
    const code = data?.error_code || data?.code
    const msg = data?.msg || data?.message || err?.message || '淘宝同步失败'
    throw new AppApiError(msg, typeof code === 'string' ? code : 'TAOBAO_SYNC_FAILED')
  }
}

export async function enqueueTaobaoOrdersSync({ force = true, storeId = null, dateWindow = null } = {}) {
  return enqueueTaobaoSync({ scope: 'orders', force, storeId, dateWindow })
}

export async function enqueueTaobaoProductsSync({ force = true, storeId = null } = {}) {
  return enqueueTaobaoSync({ scope: 'products', force, storeId })
}

export async function enqueueTaobaoCompassSync({ force = true, storeId = null } = {}) {
  return enqueueTaobaoSync({ scope: 'compass', force, storeId })
}

export async function fetchTaobaoSyncJob(jobId) {
  const res = await service.get(`/api/taobao/sync/${encodeURIComponent(jobId)}`, {
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? {}
}

export async function pollTaobaoSyncJob(jobId, { timeoutMs = 900000, intervalMs = 2000 } = {}) {
  const deadline = Date.now() + Math.max(5000, timeoutMs)
  let delay = Math.max(800, intervalMs)
  while (Date.now() < deadline) {
    const job = await fetchTaobaoSyncJob(jobId)
    const status = String(job?.status || '').toLowerCase()
    if (['success', 'failed', 'partial'].includes(status)) {
      if (status === 'failed') {
        throw new AppApiError(
          job.error_message || job.message || '淘宝同步失败',
          job.error_code || 'TAOBAO_SYNC_FAILED',
        )
      }
      return job
    }
    await new Promise((r) => setTimeout(r, delay))
    delay = Math.min(5000, Math.floor(delay * 1.25))
  }
  throw new AppApiError('淘宝同步超时，请重试', 'TAOBAO_SYNC_TIMEOUT')
}

export async function fetchTaobaoOrdersToday({ storeId } = {}) {
  const params = {}
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/taobao/orders/today', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? { items: [], synced_at: '', report_day: '' }
}

/**
 * 淘宝订单列表查询。
 * - 旧签名（syncTaobaoOrdersToday/domesticPlatforms 调用）：仅传 `dateWindow`，走 date_window 参数。
 * - 新签名（对齐 fetchAlibaba1688Orders）：传 `startDate/endDate`，并支持 status/keyword/page/pageSize 后端分页。
 */
export async function fetchTaobaoOrders({
  storeId,
  dateWindow = null,
  startDate = null,
  endDate = null,
  status = '',
  keyword = '',
  page = 1,
  pageSize = 20,
} = {}) {
  const params = {}
  if (startDate && endDate) {
    params.start_date = startDate
    params.end_date = endDate
    params.status = status
    params.keyword = keyword
    params.page = page
    params.page_size = pageSize
  } else {
    params.date_window = dateWindow || 'today'
  }
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/taobao/orders', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? { items: [], synced_at: '', report_day: '' }
}

/** 店铺经营总览（对齐 fetchAlibaba1688OrderOverview）：仅 selectedStoreId === 'all' 时调用。 */
export async function fetchTaobaoOrderOverview({ startDate, endDate } = {}) {
  const res = await service.get('/api/taobao/operations/overview', {
    params: { start_date: startDate, end_date: endDate },
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? {}
}

/** 经营汇总指标（对齐 fetchAlibaba1688OrderSummary）。 */
export async function fetchTaobaoOrderSummary({ startDate, endDate, storeId } = {}) {
  const params = { start_date: startDate, end_date: endDate }
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/taobao/operations/summary', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

/** 销售额 / 订单趋势（对齐 fetchAlibaba1688OrderTrend）。 */
export async function fetchTaobaoOrderTrend({ startDate, endDate, storeId } = {}) {
  const params = { start_date: startDate, end_date: endDate }
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/taobao/operations/trend', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? []
}

export async function syncTaobaoOrdersToday(stores, options = {}) {
  const force = options.force !== false
  const refresh = options.refresh === true
  const storeId = options.storeId || null
  const dateWindow = options.dateWindow || 'today'
  if (refresh) {
    const queued = await enqueueTaobaoOrdersSync({ force, storeId, dateWindow })
    const jobId = queued?.id || queued?.job_id
    if (!jobId) {
      throw new AppApiError('未返回同步任务 ID', 'TAOBAO_SYNC_FAILED')
    }
    await pollTaobaoSyncJob(jobId)
  }
  const data = dateWindow === 'today'
    ? await fetchTaobaoOrdersToday({ storeId })
    : await fetchTaobaoOrders({ storeId, dateWindow })
  const items = Array.isArray(data?.items) ? data.items : []
  return {
    success: true,
    message: refresh ? `已同步淘宝订单（${dateWindow}）${items.length} 条` : undefined,
    data: {
      orders: items,
      syncedAt: data?.synced_at || '',
    },
  }
}

export async function fetchTaobaoProducts({ storeId } = {}) {
  const params = {}
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/taobao/products', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? { items: [], synced_at: '', count: 0 }
}

export async function syncTaobaoProducts(options = {}) {
  const force = options.force !== false
  const storeId = options.storeId || null
  const queued = await enqueueTaobaoProductsSync({ force, storeId })
  const jobId = queued?.id || queued?.job_id
  if (!jobId) {
    throw new AppApiError('未返回同步任务 ID', 'TAOBAO_SYNC_FAILED')
  }
  const job = await pollTaobaoSyncJob(jobId)
  const data = await fetchTaobaoProducts({ storeId })
  const items = Array.isArray(data?.items) ? data.items : []
  return {
    success: true,
    message: job?.message || `已同步淘宝商品 ${items.length} 条`,
    data: {
      products: items,
      syncedAt: data?.synced_at || '',
      productsCount: job?.products_count ?? items.length,
    },
  }
}

export async function fetchTaobaoCompass({ storeId, dateType = 1, all = false } = {}) {
  const params = {}
  if (all) {
    params.all = 1
  } else {
    params.date_type = dateType
  }
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/taobao/compass', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? { snapshot: null, snapshots: [], synced_at: '', date_type: dateType }
}

export async function syncTaobaoCompass(options = {}) {
  const force = options.force !== false
  const storeId = options.storeId || null
  const queued = await enqueueTaobaoCompassSync({ force, storeId })
  const jobId = queued?.id || queued?.job_id
  if (!jobId) {
    throw new AppApiError('未返回同步任务 ID', 'TAOBAO_SYNC_FAILED')
  }
  const job = await pollTaobaoSyncJob(jobId)
  const data = await fetchTaobaoCompass({ storeId, all: true })
  const snapshots = Array.isArray(data?.snapshots) ? data.snapshots : []
  const realtime = snapshots.find((s) => Number(s.dateType) === 1) || snapshots[0] || data?.snapshot || null
  return {
    success: true,
    message: job?.message || '已同步淘宝生意参谋',
    data: {
      snapshot: realtime,
      snapshots,
      syncedAt: data?.synced_at || realtime?.syncedAt || '',
    },
  }
}

function normalizeIssueDto(row) {
  if (!row || typeof row !== 'object') return {}
  const severity = row.severity || row.priority || 'medium'
  const productImage = row.productImage || row.product_image || row.mainImage || row.main_image || ''
  return {
    ...row,
    id: row.id,
    storeId: row.storeId || row.store_id || '',
    type: row.type || '',
    typeLabel: row.typeLabel || row.type_label || '',
    sku: row.sku || '',
    productName: row.productName || row.product_name || '',
    productImage,
    mainImage: productImage,
    detail: row.detail || '',
    severity,
    priority: severity,
    resolved: row.resolved === true || row.resolved === 1,
    reportedAt: row.reportedAt || row.reported_at || '',
    resolvedAt: row.resolvedAt || row.resolved_at || '',
    note: row.note || row.resolveNote || '',
    externalId: row.externalId || row.external_id || '',
    source: row.source || '',
  }
}

export async function enqueueTaobaoIssuesSync({ force = true, storeId = null } = {}) {
  return enqueueTaobaoSync({ scope: 'issues', force, storeId })
}

export async function fetchTaobaoIssues({ storeId } = {}) {
  const params = {}
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/taobao/issues', { params, skipGlobalErrorToast: true })
  const data = res?.data ?? res ?? {}
  const items = Array.isArray(data.items) ? data.items.map(normalizeIssueDto) : []
  return {
    items,
    synced_at: data.synced_at || '',
    total: data.total ?? items.length,
  }
}

export async function syncTaobaoIssues(options = {}) {
  const force = options.force !== false
  const storeId = options.storeId || null
  const refresh = options.refresh !== false
  if (refresh) {
    const queued = await enqueueTaobaoIssuesSync({ force, storeId })
    const jobId = queued?.id || queued?.job_id
    if (!jobId) {
      throw new AppApiError('未返回同步任务 ID', 'TAOBAO_SYNC_FAILED')
    }
    const job = await pollTaobaoSyncJob(jobId, { timeoutMs: 600000 })
    const data = await fetchTaobaoIssues({ storeId })
    return {
      success: true,
      message: job?.message || `已同步淘宝工单预警 ${data.items.length} 条`,
      data: {
        issues: data.items,
        syncedAt: data.synced_at || '',
        issuesCount: job?.issues_count ?? data.items.length,
        partial: String(job?.status || '').toLowerCase() === 'partial',
      },
    }
  }
  const data = await fetchTaobaoIssues({ storeId })
  return {
    success: true,
    data: {
      issues: data.items,
      syncedAt: data.synced_at || '',
    },
  }
}

export async function resolveTaobaoIssueApi(id, payload = {}) {
  const res = await service.patch(
    `/api/taobao/issues/${encodeURIComponent(id)}`,
    {
      resolved: payload.resolved !== false,
      note: payload.note || payload.resolveNote || '',
    },
    { skipGlobalErrorToast: true },
  )
  return { success: true, data: normalizeIssueDto(res?.data ?? res) }
}

/** 同行爆款抓取同步入口（对齐 enqueueAlibaba1688PeerBestsellersSync）。 */
export async function enqueueTaobaoPeerBestsellersSync({ force = true, storeId = null } = {}) {
  return enqueueTaobaoSync({ scope: 'peer_bestsellers', force, storeId })
}

/** 商品分析列表（爆款/今日爆款/近期销量，对齐 fetchAlibaba1688ProductAnalytics）。 */
export async function fetchTaobaoProductAnalytics({ type, storeId } = {}) {
  const params = {}
  if (type) params.type = type
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/taobao/product-analytics', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? { items: [], total: 0 }
}

/** 同行爆款追踪列表（对齐 fetchAlibaba1688PeerBestsellers）。 */
export async function fetchTaobaoPeerBestsellers({ storeId, page = 1, pageSize = 10 } = {}) {
  const params = { page, page_size: pageSize }
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/taobao/peer-bestsellers', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? { items: [], total: 0 }
}
