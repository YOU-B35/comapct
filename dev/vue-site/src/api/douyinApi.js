import { service } from './request'
import { hasBackendSession } from './backendSession'
import { AppApiError } from '@/utils/appErrorCode'
import { runDouyinFullSync, FULL_SYNC_STEP_IDS, FULL_SYNC_STEP_LABELS } from './douyinFullSync'

export { FULL_SYNC_STEP_IDS, FULL_SYNC_STEP_LABELS }

export function canUseDouyinBackend(auth) {
  return hasBackendSession(auth)
}

export async function fetchDouyinSession() {
  const res = await service.get('/api/douyin/session', { skipGlobalErrorToast: true })
  return res?.data ?? res ?? {}
}

export async function enqueueDouyinLogin({ storeId } = {}) {
  const res = await service.post('/api/douyin/login/open', {}, {
    params: storeId && storeId !== 'all' ? { storeId } : {},
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? {}
}

export async function enqueueDouyinSessionProbe({ storeId } = {}) {
  const res = await service.post('/api/douyin/session/probe', {}, {
    params: storeId && storeId !== 'all' ? { storeId } : {},
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? {}
}

/** Poll Douyin seller session until ready (HelperStatusBar). */
export async function pollDouyinSessionUntilReady({
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
    await enqueueDouyinSessionProbe({ storeId })
  } catch {
    // ignore; still poll session
  }
  while (Date.now() < deadline) {
    if (signal?.aborted) {
      throw new DOMException('Aborted', 'AbortError')
    }
    const session = await fetchDouyinSession()
    if (session?.ready || session?.logged_in) {
      return session
    }
    await new Promise((r) => setTimeout(r, delay))
    delay = Math.min(maxIntervalMs, Math.floor(delay * 1.25))
  }
  return fetchDouyinSession()
}

async function enqueueDouyinSync({
  scope,
  force = true,
  storeId = null,
  categoryQuery = null,
  categoryId = null,
  pool = null,
  sortField = null,
} = {}) {
  const body = { scope: scope || 'orders', force: !!force }
  if (storeId) body.store_id = storeId
  if (categoryQuery) body.category_query = categoryQuery
  if (categoryId) body.category_id = categoryId
  if (pool) body.pool = pool
  if (sortField) body.sort_field = sortField
  try {
    const res = await service.post('/api/douyin/sync', body, { skipGlobalErrorToast: true })
    return res?.data ?? res ?? {}
  } catch (err) {
    const data = err?.response?.data
    const code = data?.error_code || data?.code
    const msg = data?.msg || data?.message || err?.message || '抖音同步失败'
    throw new AppApiError(msg, typeof code === 'string' ? code : 'DY_SYNC_FAILED')
  }
}

export async function enqueueDouyinOrdersSync({ force = true, storeId = null } = {}) {
  return enqueueDouyinSync({ scope: 'orders', force, storeId })
}

export async function enqueueDouyinProductsSync({ force = true, storeId = null } = {}) {
  return enqueueDouyinSync({ scope: 'products', force, storeId })
}

export async function fetchDouyinSyncJob(jobId) {
  const res = await service.get(`/api/douyin/sync/${encodeURIComponent(jobId)}`, {
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? {}
}

export async function pollDouyinSyncJob(jobId, { timeoutMs = 900000, intervalMs = 2000 } = {}) {
  const deadline = Date.now() + Math.max(5000, timeoutMs)
  let delay = Math.max(800, intervalMs)
  while (Date.now() < deadline) {
    const job = await fetchDouyinSyncJob(jobId)
    const status = String(job?.status || '').toLowerCase()
    if (['success', 'failed', 'partial'].includes(status)) {
      if (status === 'failed') {
        throw new AppApiError(
          job.error_message || job.message || '抖音同步失败',
          job.error_code || 'DY_SYNC_FAILED',
        )
      }
      return job
    }
    await new Promise((r) => setTimeout(r, delay))
    delay = Math.min(5000, Math.floor(delay * 1.25))
  }
  throw new AppApiError('抖音同步超时，请重试', 'DY_SYNC_TIMEOUT')
}

export async function fetchDouyinOrdersToday({ storeId } = {}) {
  const params = {}
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/douyin/orders/today', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? { items: [], synced_at: '', report_day: '' }
}

export async function syncDouyinOrdersToday(stores, options = {}) {
  const force = options.force !== false
  const refresh = options.refresh === true
  const storeId = options.storeId || null
  if (refresh) {
    const queued = await enqueueDouyinOrdersSync({ force, storeId })
    const jobId = queued?.id || queued?.job_id
    if (!jobId) {
      throw new AppApiError('未返回同步任务 ID', 'DY_SYNC_FAILED')
    }
    await pollDouyinSyncJob(jobId)
  }
  const data = await fetchDouyinOrdersToday({ storeId })
  const items = Array.isArray(data?.items) ? data.items : []
  return {
    success: true,
    message: refresh ? `已同步抖音近24小时订单 ${items.length} 条` : undefined,
    data: {
      orders: items,
      syncedAt: data?.synced_at || '',
    },
  }
}

export async function fetchDouyinProducts({ storeId } = {}) {
  const params = {}
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/douyin/products', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? { items: [], synced_at: '', count: 0 }
}

export async function syncDouyinProducts(options = {}) {
  const force = options.force !== false
  const storeId = options.storeId || null
  const queued = await enqueueDouyinProductsSync({ force, storeId })
  const jobId = queued?.id || queued?.job_id
  if (!jobId) {
    throw new AppApiError('未返回同步任务 ID', 'DY_SYNC_FAILED')
  }
  const job = await pollDouyinSyncJob(jobId)
  const data = await fetchDouyinProducts({ storeId })
  const items = Array.isArray(data?.items) ? data.items : []
  return {
    success: true,
    message: job?.message || `已同步抖音商品 ${items.length} 条`,
    data: {
      products: items,
      syncedAt: data?.synced_at || '',
      productsCount: job?.products_count ?? items.length,
    },
  }
}

export async function enqueueDouyinCompassSync({ force = true, storeId = null } = {}) {
  return enqueueDouyinSync({ scope: 'compass', force, storeId })
}

export async function fetchDouyinCompass({ storeId, dateType = 1, all = false } = {}) {
  const params = {}
  if (all) {
    params.all = 1
  } else {
    params.date_type = dateType
  }
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/douyin/compass', { params, skipGlobalErrorToast: true })
  return res?.data ?? res ?? { snapshot: null, snapshots: [], synced_at: '', date_type: dateType }
}

export async function syncDouyinCompass(options = {}) {
  const force = options.force !== false
  const storeId = options.storeId || null
  const queued = await enqueueDouyinCompassSync({ force, storeId })
  const jobId = queued?.id || queued?.job_id
  if (!jobId) {
    throw new AppApiError('未返回同步任务 ID', 'DY_SYNC_FAILED')
  }
  const job = await pollDouyinSyncJob(jobId)
  const data = await fetchDouyinCompass({ storeId, all: true })
  const snapshots = Array.isArray(data?.snapshots) ? data.snapshots : []
  const realtime = snapshots.find((s) => Number(s.dateType) === 1) || snapshots[0] || data?.snapshot || null
  return {
    success: true,
    message: job?.message || '已同步抖店罗盘（实时 / 近1天 / 近7天 / 近30天）',
    data: {
      snapshot: realtime,
      snapshots,
      syncedAt: data?.synced_at || realtime?.syncedAt || '',
    },
  }
}

export async function enqueueDouyinOpportunitySync({
  force = true,
  storeId = null,
  categoryQuery = null,
  categoryId = null,
  pool = 'potential',
  sortField = 'MATCH_DEGREE',
} = {}) {
  return enqueueDouyinSync({
    scope: 'opportunity',
    force,
    storeId,
    categoryQuery,
    categoryId,
    pool,
    sortField,
  })
}

export async function fetchDouyinOpportunityProducts({
  storeId,
  categoryKey,
  q,
  pool,
  sortField,
} = {}) {
  const params = {}
  if (storeId && storeId !== 'all') params.store_id = storeId
  if (categoryKey) params.category_key = categoryKey
  if (q) params.q = q
  if (pool) params.pool = pool
  if (sortField) params.sort_field = sortField
  const res = await service.get('/api/douyin/opportunity/products', {
    params,
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? { items: [], synced_at: '', count: 0 }
}

export async function fetchDouyinOpportunityOverview(id) {
  const res = await service.get(
    `/api/douyin/opportunity/products/${encodeURIComponent(id)}/overview`,
    { skipGlobalErrorToast: true },
  )
  return res?.data ?? res ?? {}
}

export async function syncDouyinOpportunity(options = {}) {
  const force = options.force !== false
  const storeId = options.storeId || null
  const categoryQuery = options.categoryQuery || null
  const categoryId = options.categoryId || null
  const pool = options.pool || 'potential'
  const sortField = options.sortField || 'MATCH_DEGREE'
  const queued = await enqueueDouyinOpportunitySync({
    force,
    storeId,
    categoryQuery,
    categoryId,
    pool,
    sortField,
  })
  const jobId = queued?.id || queued?.job_id
  if (!jobId) {
    throw new AppApiError('未返回同步任务 ID', 'DY_SYNC_FAILED')
  }
  const job = await pollDouyinSyncJob(jobId, { timeoutMs: 900000 })
  const data = await fetchDouyinOpportunityProducts({ storeId, pool, sortField })
  const items = Array.isArray(data?.items) ? data.items : []
  return {
    success: true,
    message: job?.message || `已同步商机中心 Top${items.length}`,
    data: {
      products: items,
      syncedAt: data?.synced_at || '',
      categoryKey: data?.category_key || '',
      categoryName: data?.category_name || '',
      pool: data?.pool || pool,
      sortField: data?.sort_field || sortField,
      count: items.length,
    },
  }
}

export async function enqueueDouyinCompassProductRankSync({ force = true, storeId = null } = {}) {
  return enqueueDouyinSync({ scope: 'compass_product_rank', force, storeId })
}

export async function fetchDouyinCompassProductRanks({
  storeId,
  board = 'total',
  dateWindow = 'today',
} = {}) {
  const params = { board, date_window: dateWindow }
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/douyin/compass-product-ranks', {
    params,
    skipGlobalErrorToast: true,
  })
  return res?.data ?? res ?? { items: [], synced_at: '', total: 0 }
}

export async function syncDouyinCompassProductRank(options = {}) {
  const force = options.force !== false
  const storeId = options.storeId || null
  const board = options.board || 'total'
  const dateWindow = options.dateWindow || 'today'
  const queued = await enqueueDouyinCompassProductRankSync({ force, storeId })
  const jobId = queued?.id || queued?.job_id
  if (!jobId) {
    throw new AppApiError('未返回同步任务 ID', 'DY_SYNC_FAILED')
  }
  const job = await pollDouyinSyncJob(jobId, { timeoutMs: 900000 })
  const data = await fetchDouyinCompassProductRanks({ storeId, board, dateWindow })
  const items = Array.isArray(data?.items) ? data.items : []
  return {
    success: true,
    message: job?.message || '已同步罗盘商品榜',
    data: {
      items,
      syncedAt: data?.synced_at || '',
      board: data?.board || board,
      dateWindow: data?.date_window || dateWindow,
      reportDay: data?.report_day || '',
      categoryName: data?.category_name || '',
      total: data?.total ?? items.length,
    },
  }
}

function normalizeIssueDto(row = {}) {
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

export async function enqueueDouyinIssuesSync({ force = true, storeId = null } = {}) {
  return enqueueDouyinSync({ scope: 'issues', force, storeId })
}

export async function fetchDouyinIssues({ storeId } = {}) {
  const params = {}
  if (storeId && storeId !== 'all') params.store_id = storeId
  const res = await service.get('/api/douyin/issues', { params, skipGlobalErrorToast: true })
  const data = res?.data ?? res ?? {}
  const items = Array.isArray(data.items) ? data.items.map(normalizeIssueDto) : []
  return {
    items,
    synced_at: data.synced_at || '',
    total: data.total ?? items.length,
  }
}

export async function syncDouyinIssues(options = {}) {
  const force = options.force !== false
  const storeId = options.storeId || null
  const refresh = options.refresh !== false
  if (refresh) {
    const queued = await enqueueDouyinIssuesSync({ force, storeId })
    const jobId = queued?.id || queued?.job_id
    if (!jobId) {
      throw new AppApiError('未返回同步任务 ID', 'DY_SYNC_FAILED')
    }
    const job = await pollDouyinSyncJob(jobId, { timeoutMs: 600000 })
    const data = await fetchDouyinIssues({ storeId })
    return {
      success: true,
      message: job?.message || `已同步内容预警 ${data.items.length} 条`,
      data: {
        issues: data.items,
        syncedAt: data.synced_at || '',
        issuesCount: job?.issues_count ?? data.items.length,
        partial: String(job?.status || '').toLowerCase() === 'partial',
      },
    }
  }
  const data = await fetchDouyinIssues({ storeId })
  return {
    success: true,
    data: {
      issues: data.items,
      syncedAt: data.synced_at || '',
    },
  }
}

export async function resolveDouyinIssueApi(id, payload = {}) {
  const res = await service.patch(
    `/api/douyin/issues/${encodeURIComponent(id)}`,
    {
      resolved: payload.resolved !== false,
      note: payload.note || payload.resolveNote || '',
    },
    { skipGlobalErrorToast: true },
  )
  return { success: true, data: normalizeIssueDto(res?.data ?? res) }
}

export async function syncDouyinFull(options = {}) {
  const {
    storeId = null,
    force = true,
    pool,
    sortField,
    categoryQuery,
    categoryId,
    board,
    dateWindow,
    onProgress,
    // injectable for tests
    runners: overrideRunners,
  } = options

  const ctx = { storeId, force, pool, sortField, categoryQuery, categoryId, board, dateWindow }

  const defaultRunners = {
    compass: async (c) => {
      try {
        const res = await syncDouyinCompass({ force: c.force, storeId: c.storeId })
        return { ok: true, message: res?.message }
      } catch (e) {
        return { ok: false, error: e?.message || String(e) }
      }
    },
    compass_product_rank: async (c) => {
      try {
        const res = await syncDouyinCompassProductRank({
          force: c.force,
          storeId: c.storeId,
          board: c.board,
          dateWindow: c.dateWindow,
        })
        return { ok: true, message: res?.message }
      } catch (e) {
        return { ok: false, error: e?.message || String(e) }
      }
    },
    opportunity: async (c) => {
      try {
        const res = await syncDouyinOpportunity({
          force: c.force,
          storeId: c.storeId,
          pool: c.pool,
          sortField: c.sortField,
          categoryQuery: c.categoryQuery,
          categoryId: c.categoryId,
        })
        return { ok: true, message: res?.message }
      } catch (e) {
        return { ok: false, error: e?.message || String(e) }
      }
    },
    products: async (c) => {
      try {
        const res = await syncDouyinProducts({ force: c.force, storeId: c.storeId })
        return { ok: true, message: res?.message }
      } catch (e) {
        return { ok: false, error: e?.message || String(e) }
      }
    },
    orders: async (c) => {
      try {
        // refresh:true 才真正 enqueue；stores 可传 []，由后端 storeId 决定
        const res = await syncDouyinOrdersToday([], {
          force: c.force,
          storeId: c.storeId,
          refresh: true,
        })
        return { ok: true, message: res?.message }
      } catch (e) {
        return { ok: false, error: e?.message || String(e) }
      }
    },
    issues: async (c) => {
      try {
        const res = await syncDouyinIssues({
          force: c.force,
          storeId: c.storeId,
          refresh: true,
        })
        return { ok: true, message: res?.message }
      } catch (e) {
        return { ok: false, error: e?.message || String(e) }
      }
    },
  }

  return runDouyinFullSync(ctx, overrideRunners || defaultRunners, onProgress)
}
