import { service } from './request'
import { hasBackendSession } from './backendSession'
import { AppApiError } from '@/utils/appErrorCode'

export function canUsePddBackend(auth) {
  return hasBackendSession(auth)
}

export async function fetchPddSession({ storeId } = {}) {
  const params = {}
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/pdd/session', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

export async function enqueuePddLogin({ storeId } = {}) {
  const res = await service.post('/api/pdd/login/open', {}, {
    params: storeId && storeId !== 'all' ? { storeId } : {},
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? {}
}

export async function enqueuePddSessionProbe({ storeId } = {}) {
  const res = await service.post('/api/pdd/session/probe', {}, {
    params: storeId && storeId !== 'all' ? { storeId } : {},
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? {}
}

/** Poll PDD seller session until ready (HelperStatusBar). */
export async function pollPddSessionUntilReady({
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
    await enqueuePddSessionProbe({ storeId })
  } catch {
    // ignore; still poll session
  }
  while (Date.now() < deadline) {
    if (signal?.aborted) {
      throw new DOMException('Aborted', 'AbortError')
    }
    const session = await fetchPddSession({ storeId })
    if (session?.ready || session?.logged_in) {
      return session
    }
    await new Promise((r) => setTimeout(r, delay))
    delay = Math.min(maxIntervalMs, Math.floor(delay * 1.25))
  }
  return fetchPddSession({ storeId })
}

async function enqueuePddSync({
  scope,
  force = true,
  storeId = null,
  dateWindow = null,
} = {}) {
  const body = { scope: scope || 'orders', force: !!force }
  if (storeId) body.store_id = storeId
  if (dateWindow) body.date_window = dateWindow
  try {
    const res = await service.post('/api/pdd/sync', body, { skipGlobalErrorToast: true })
    return res?.data ?? res ?? {}
  } catch (err) {
    const data = err?.response?.data
    const code = data?.error_code || data?.code
    const msg = data?.msg || data?.message || err?.message || '拼多多同步失败'
    throw new AppApiError(msg, typeof code === 'string' ? code : 'PDD_SYNC_FAILED')
  }
}

export async function enqueuePddOrdersSync({ force = true, storeId = null, dateWindow = null } = {}) {
  return enqueuePddSync({ scope: 'orders', force, storeId, dateWindow })
}

export async function enqueuePddProductsSync({ force = true, storeId = null } = {}) {
  return enqueuePddSync({ scope: 'products', force, storeId })
}

export async function enqueuePddCompassSync({ force = true, storeId = null } = {}) {
  return enqueuePddSync({ scope: 'compass', force, storeId })
}

export async function fetchPddSyncJob(jobId) {
  const res = await service.get(`/api/pdd/sync/${encodeURIComponent(jobId)}`, {
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? {}
}

export async function pollPddSyncJob(jobId, { timeoutMs = 900000, intervalMs = 2000 } = {}) {
  const deadline = Date.now() + Math.max(5000, timeoutMs)
  let delay = Math.max(800, intervalMs)
  while (Date.now() < deadline) {
    const job = await fetchPddSyncJob(jobId)
    const status = String(job?.status || '').toLowerCase()
    if (['success', 'failed', 'partial'].includes(status)) {
      if (status === 'failed') {
        throw new AppApiError(
          job.error_message || job.message || '拼多多同步失败',
          job.error_code || 'PDD_SYNC_FAILED',
        )
      }
      return job
    }
    await new Promise((r) => setTimeout(r, delay))
    delay = Math.min(5000, Math.floor(delay * 1.25))
  }
  throw new AppApiError('拼多多同步超时，请重试', 'PDD_SYNC_TIMEOUT')
}

function normalizePddOrderRow(row = {}) {
  if (!row || typeof row !== 'object') return row
  return {
    ...row,
    orderNo: row.orderNo ?? row.order_no ?? '',
    productName: row.productName ?? row.product_name ?? '',
    skuText: row.skuText ?? row.sku_text ?? '',
    unitPrice: row.unitPrice ?? row.unit_price ?? '',
    itemAmount: row.itemAmount ?? row.item_amount ?? '',
    paidAmount: row.paidAmount ?? row.paid_amount ?? '',
    refundedAmount: row.refundedAmount ?? row.refunded_amount ?? '',
    paidAt: row.paidAt ?? row.paid_at ?? '',
    refundedAt: row.refundedAt ?? row.refunded_at ?? '',
    buyerMasked: row.buyerMasked ?? row.buyer_masked ?? '',
    imageUrl: row.imageUrl ?? row.image_url ?? '',
    status: row.status ?? row.order_status ?? '',
  }
}

function normalizePddProductRow(row = {}) {
  if (!row || typeof row !== 'object') return row
  return {
    ...row,
    productId: row.productId ?? row.product_id ?? '',
    productName: row.productName ?? row.product_name ?? '',
    goodsId: row.goodsId ?? row.product_id ?? row.productId ?? '',
    imageUrl: row.imageUrl ?? row.main_image ?? row.image_url ?? '',
    syncedAt: row.syncedAt ?? row.synced_at ?? '',
    sales: row.sales ?? row.sold_quantity ?? 0,
    stock: row.stock ?? row.quantity ?? 0,
  }
}

export async function fetchPddOrdersToday({ storeId } = {}) {
  const params = {}
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/pdd/orders/today', { params, skipGlobalErrorToast: true })
  const data = res?.data ?? res ?? { items: [], synced_at: '', report_day: '' }
  const items = Array.isArray(data.items) ? data.items.map(normalizePddOrderRow) : []
  return { ...data, items }
}

/**
 * 拼多多订单列表查询。
 * - 旧签名（syncPddOrdersToday/domesticPlatforms 调用）：仅传 `dateWindow`，走 date_window 参数。
 * - 新签名（对齐 fetchAlibaba1688Orders）：传 `startDate/endDate`，并支持 status/keyword/page/pageSize 后端分页。
 */
export async function fetchPddOrders({
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
  const res = await service.get('/api/pdd/orders', { params, skipGlobalErrorToast: true })
  const data = res?.data ?? res ?? { items: [], synced_at: '', report_day: '' }
  const items = Array.isArray(data.items) ? data.items.map(normalizePddOrderRow) : []
  return { ...data, items }
}

/** 店铺经营总览（对齐 fetchAlibaba1688OrderOverview）：仅 selectedStoreId === 'all' 时调用。 */
export async function fetchPddOrderOverview({ startDate, endDate } = {}) {
  const res = await service.get('/api/pdd/operations/overview', {
    params: { start_date: startDate, end_date: endDate },
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? {}
}

/** 经营汇总指标（对齐 fetchAlibaba1688OrderSummary）。 */
export async function fetchPddOrderSummary({ startDate, endDate, storeId } = {}) {
  const params = { start_date: startDate, end_date: endDate }
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/pdd/operations/summary', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

/** 销售额 / 订单趋势（对齐 fetchAlibaba1688OrderTrend）。 */
export async function fetchPddOrderTrend({ startDate, endDate, storeId } = {}) {
  const params = { start_date: startDate, end_date: endDate }
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/pdd/operations/trend', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? []
}

export async function syncPddOrdersToday(stores, options = {}) {
  const force = options.force !== false
  const refresh = options.refresh === true
  const storeId = options.storeId || null
  const dateWindow = options.dateWindow || 'today'
  if (refresh) {
    const queued = await enqueuePddOrdersSync({ force, storeId, dateWindow })
    const jobId = queued?.id || queued?.job_id
    if (!jobId) {
      throw new AppApiError('未返回同步任务 ID', 'PDD_SYNC_FAILED')
    }
    await pollPddSyncJob(jobId)
  }
  const data = dateWindow === 'today'
    ? await fetchPddOrdersToday({ storeId })
    : await fetchPddOrders({ storeId, dateWindow })
  const items = Array.isArray(data?.items) ? data.items : []
  return {
    success: true,
    message: refresh ? `已同步拼多多订单（${dateWindow}）${items.length} 条` : undefined,
    data: {
      orders: items,
      syncedAt: data?.synced_at || '',
    },
  }
}

export async function fetchPddProducts({ storeId } = {}) {
  const params = {}
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/pdd/products', { params, skipGlobalErrorToast: true })
  const data = res?.data ?? res ?? { items: [], synced_at: '', count: 0 }
  const items = Array.isArray(data.items) ? data.items.map(normalizePddProductRow) : []
  return { ...data, items }
}

export async function syncPddProducts(options = {}) {
  const force = options.force !== false
  const storeId = options.storeId || null
  const queued = await enqueuePddProductsSync({ force, storeId })
  const jobId = queued?.id || queued?.job_id
  if (!jobId) {
    throw new AppApiError('未返回同步任务 ID', 'PDD_SYNC_FAILED')
  }
  const job = await pollPddSyncJob(jobId)
  const data = await fetchPddProducts({ storeId })
  const items = Array.isArray(data?.items) ? data.items : []
  return {
    success: true,
    message: job?.message || `已同步拼多多商品 ${items.length} 条`,
    data: {
      products: items,
      syncedAt: data?.synced_at || '',
      productsCount: job?.products_count ?? items.length,
    },
  }
}

export async function fetchPddCompass({ storeId, dateType = 1, all = false } = {}) {
  const params = {}
  if (all) {
    params.all = 1
  } else {
    params.date_type = dateType
  }
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/pdd/compass', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? { snapshot: null, snapshots: [], synced_at: '', date_type: dateType }
}

export async function syncPddCompass(options = {}) {
  const force = options.force !== false
  const storeId = options.storeId || null
  const queued = await enqueuePddCompassSync({ force, storeId })
  const jobId = queued?.id || queued?.job_id
  if (!jobId) {
    throw new AppApiError('未返回同步任务 ID', 'PDD_SYNC_FAILED')
  }
  const job = await pollPddSyncJob(jobId)
  const data = await fetchPddCompass({ storeId, all: true })
  const snapshots = Array.isArray(data?.snapshots) ? data.snapshots : []
  const realtime = snapshots.find((s) => Number(s.dateType) === 1) || snapshots[0] || data?.snapshot || null
  return {
    success: true,
    message: job?.message || '已同步拼多多经营罗盘',
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

export async function enqueuePddIssuesSync({ force = true, storeId = null } = {}) {
  return enqueuePddSync({ scope: 'issues', force, storeId })
}

export async function fetchPddIssues({ storeId } = {}) {
  const params = {}
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/pdd/issues', { params, skipGlobalErrorToast: true })
  const data = res?.data ?? res ?? {}
  const items = Array.isArray(data.items) ? data.items.map(normalizeIssueDto) : []
  return {
    items,
    synced_at: data.synced_at || '',
    total: data.total ?? items.length,
  }
}

export async function syncPddIssues(options = {}) {
  const force = options.force !== false
  const storeId = options.storeId || null
  const refresh = options.refresh !== false
  if (refresh) {
    const queued = await enqueuePddIssuesSync({ force, storeId })
    const jobId = queued?.id || queued?.job_id
    if (!jobId) {
      throw new AppApiError('未返回同步任务 ID', 'PDD_SYNC_FAILED')
    }
    const job = await pollPddSyncJob(jobId, { timeoutMs: 600000 })
    const data = await fetchPddIssues({ storeId })
    return {
      success: true,
      message: job?.message || `已同步拼多多工单预警 ${data.items.length} 条`,
      data: {
        issues: data.items,
        syncedAt: data.synced_at || '',
        issuesCount: job?.issues_count ?? data.items.length,
        partial: String(job?.status || '').toLowerCase() === 'partial',
      },
    }
  }
  const data = await fetchPddIssues({ storeId })
  return {
    success: true,
    data: {
      issues: data.items,
      syncedAt: data.synced_at || '',
    },
  }
}

export async function resolvePddIssueApi(id, payload = {}) {
  const res = await service.patch(
    `/api/pdd/issues/${encodeURIComponent(id)}`,
    {
      resolved: payload.resolved !== false,
      note: payload.note || payload.resolveNote || '',
    },
    { skipGlobalErrorToast: true },
  )
  return { success: true, data: normalizeIssueDto(res?.data ?? res) }
}

/** 同行爆款抓取同步入口（对齐 enqueueAlibaba1688PeerBestsellersSync）。 */
export async function enqueuePddPeerBestsellersSync({ force = true, storeId = null } = {}) {
  return enqueuePddSync({ scope: 'peer_bestsellers', force, storeId })
}

/** 商品分析列表（爆款/今日爆款/近期销量，对齐 fetchAlibaba1688ProductAnalytics）。 */
export async function fetchPddProductAnalytics({ type, storeId } = {}) {
  const params = {}
  if (type) params.type = type
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/pdd/product-analytics', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? { items: [], total: 0 }
}

/** 同行爆款追踪列表（对齐 fetchAlibaba1688PeerBestsellers）。 */
export async function fetchPddPeerBestsellers({ storeId, page = 1, pageSize = 10 } = {}) {
  const params = { page, page_size: pageSize }
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/pdd/peer-bestsellers', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? { items: [], total: 0 }
}
