import axios from 'axios'
import { AppApiError, getAppErrorMessage, toAppApiError } from '@/utils/appErrorCode'
import {
  assertPlatformCrawlAllowed,
  applyCrawlRequestFlags,
  isPlatformSyncBatchOptions,
  markPlatformCrawlOnSuccess,
  normalizeCrawlOptions,
  PLATFORM_SYNC_BATCH_GUARD,
  throwIfCrawlCooldownResponse,
} from '@/utils/platformSyncCooldown'
import { service, getAccessToken } from './request'
import { isTemuBackendEnabled, TEMU_API_BASE_URL } from './config'
import { isBackendLinked } from './backendSession'
import { parseAmazonAmount, isValidAmazonProduct } from '@/utils/amazonBoss'

const SYNC_POLL_MS = 2000
const SYNC_MAX_WAIT_MS = 2400000

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function unwrapData(res) {
  return res?.data ?? res
}

function mapMetric(row) {
  if (!row) return row
  const storeId = row.store_id ?? row.storeId ?? ''
  return {
    id: row.id || `${storeId}:${row.metric_key || row.metricKey || 'metric'}`,
    storeId,
    metricKey: row.metric_key ?? row.metricKey ?? '',
    label: row.label ?? row.metric_label ?? row.metricLabel ?? '',
    value: row.value ?? row.value_text ?? row.valueText ?? '',
    threshold: row.threshold ?? row.threshold_text ?? row.thresholdText ?? '',
    status: row.status || 'normal',
    trend: row.trend || 'stable',
    reportedAt: row.reported_at ?? row.reportedAt ?? '',
    note: row.note ?? row.note_text ?? row.noteText ?? '',
  }
}

function mapMessage(row) {
  const storeId = row.store_id ?? row.storeId ?? ''
  return {
    id: row.id,
    storeId,
    buyerName: row.buyer_name ?? row.buyerName ?? '',
    orderNo: row.order_no ?? row.orderNo ?? '',
    subject: row.subject ?? '',
    preview: row.preview ?? '',
    receivedAt: row.received_at ?? row.receivedAt ?? '',
    slaHours: row.sla_hours ?? row.slaHours ?? 24,
    status: row.status || 'pending',
    repliedAt: row.replied_at ?? row.repliedAt ?? null,
    templateUsed: row.template_used ?? row.templateUsed ?? null,
    replyNote: row.reply_note ?? row.replyNote ?? '',
  }
}

function mapReview(row) {
  const storeId = row.store_id ?? row.storeId ?? ''
  return {
    id: row.id,
    storeId,
    orderNo: row.order_no ?? row.orderNo ?? '',
    asin: row.asin ?? '',
    productName: row.product_name ?? row.productName ?? '',
    rating: Number(row.rating || 0),
    content: row.content ?? '',
    reviewedAt: row.reviewed_at ?? row.reviewedAt ?? '',
    status: row.status || 'pending',
    handledAt: row.handled_at ?? row.handledAt ?? null,
  }
}

function mapCoupon(row) {
  const storeId = row.store_id ?? row.storeId ?? ''
  return {
    id: row.id,
    storeId,
    name: row.name ?? '',
    discount: row.discount ?? '',
    startAt: row.start_at ?? row.startAt ?? '',
    endAt: row.end_at ?? row.endAt ?? '',
    status: row.status || 'active',
    redemptions: row.redemptions ?? 0,
    budget: row.budget ?? 0,
    note: row.note ?? '',
  }
}

function mapNews(row) {
  const storeId = row.store_id ?? row.storeId ?? ''
  return {
    id: row.id,
    storeId,
    title: row.title ?? '',
    summary: row.summary ?? '',
    publishedAt: row.published_at ?? row.publishedAt ?? '',
    status: row.status || 'unread',
  }
}

function mapShipment(row) {
  const storeId = row.store_id ?? row.storeId ?? ''
  return {
    id: row.id,
    storeId,
    shipmentId: row.shipment_id ?? row.shipmentId ?? '',
    productName: row.product_name ?? row.productName ?? '',
    sku: row.sku ?? '',
    unitsExpected: Number(row.units_expected ?? row.unitsExpected ?? 0),
    unitsReceived: Number(row.units_received ?? row.unitsReceived ?? 0),
    destination: row.destination ?? '',
    status: row.status || 'in_transit',
    expectedAt: row.expected_at ?? row.expectedAt ?? row.eta ?? '',
    alertLevel: row.alert_level ?? row.alertLevel ?? 'normal',
    note: row.note ?? '',
  }
}

function mapCase(row) {
  const storeId = row.store_id ?? row.storeId ?? ''
  return {
    id: row.id,
    storeId,
    caseId: row.case_id ?? row.caseId ?? '',
    title: row.title ?? '',
    status: row.status || 'pending',
    openedAt: row.opened_at ?? row.openedAt ?? '',
    note: row.note ?? '',
    readAt: row.read_at ?? row.readAt ?? null,
  }
}

function mapProduct(row) {
  const storeId = row.store_id ?? row.storeId ?? ''
  return {
    id: row.id || `${storeId}:${row.asin || row.sku || row.rank}`,
    storeId,
    asin: row.asin ?? '',
    sku: row.sku ?? '',
    productName: row.product_name ?? row.productName ?? '',
    orders7d: Number(row.orders7d ?? row.orders_30d ?? 0),
    revenue7d: parseAmazonAmount(row.revenue7d ?? row.revenue_30d ?? 0),
    adSpend7d: parseAmazonAmount(row.adSpend7d ?? row.ad_spend_30d ?? 0),
    acos: Number(row.acos ?? 0),
    tacos: Number(row.tacos ?? 0),
    sessions7d: Number(row.sessions7d ?? row.page_views ?? 0),
    conversionRate: Number(row.conversion_rate ?? row.conversionRate ?? 0),
    unitsOnHand: Number(row.unitsOnHand ?? row.inventory ?? 0),
    profitMargin: row.profit_margin ?? row.profitMargin ?? null,
    currency: row.currency || 'USD',
    rank: Number(row.rank ?? row.rank_no ?? 0),
  }
}

function mapOutbound(row) {
  const storeId = row.store_id ?? row.storeId ?? ''
  return {
    id: row.id,
    storeId,
    orderNo: row.order_no ?? row.orderNo ?? '',
    asin: row.asin ?? '',
    sku: row.sku ?? '',
    productName: row.product_name ?? row.productName ?? '',
    quantity: Number(row.quantity ?? 1),
    fulfillmentType: row.fulfillment_type ?? row.fulfillmentType ?? 'fba',
    status: row.status || 'pending',
    amount: row.amount ?? '',
    currency: row.currency || 'USD',
    orderedAt: row.ordered_at ?? row.orderedAt ?? '',
    shipDeadline: row.ship_deadline ?? row.shipDeadline ?? null,
    buyerRegion: row.buyer_region ?? row.buyerRegion ?? '',
    trackingNo: row.tracking_no ?? row.trackingNo ?? '',
  }
}

function mapDailyPayload(data, stores = []) {
  const boundIds = new Set((stores || []).map((s) => s.id))
  const filterByStore = (items) =>
    (items || []).filter((item) => !boundIds.size || boundIds.has(item.storeId))

  return {
    buyerMessages: filterByStore((data?.buyer_messages || data?.buyerMessages || []).map(mapMessage)),
    accountMetrics: filterByStore((data?.account_metrics || data?.accountMetrics || []).map(mapMetric)),
    reviews: filterByStore((data?.reviews || []).map(mapReview)),
    coupons: filterByStore((data?.coupons || []).map(mapCoupon)),
    sellerNews: filterByStore((data?.seller_news || data?.sellerNews || []).map(mapNews)),
    shipments: filterByStore((data?.shipments || []).map(mapShipment)),
    cases: filterByStore((data?.cases || []).map(mapCase)),
    syncedAt: data?.synced_at ?? data?.syncedAt ?? '',
  }
}

function mapDataQuality(data) {
  const raw = data?.data_quality ?? data?.dataQuality ?? {}
  if (!raw || typeof raw !== 'object') return null
  return {
    periodDays: Number(raw.period_days ?? raw.periodDays ?? 0) || 0,
    brSource: raw.br_source ?? raw.brSource ?? '',
    inventorySource: raw.inventory_source ?? raw.inventorySource ?? '',
    adsSource: raw.ads_source ?? raw.adsSource ?? '',
    brRows: Number(raw.br_rows ?? raw.brRows ?? 0) || 0,
    inventoryRows: Number(raw.inventory_rows ?? raw.inventoryRows ?? 0) || 0,
    adsRows: Number(raw.ads_rows ?? raw.adsRows ?? 0) || 0,
    productsWithRevenue: Number(raw.products_with_revenue ?? raw.productsWithRevenue ?? 0) || 0,
    productsWithAdSpend: Number(raw.products_with_ad_spend ?? raw.productsWithAdSpend ?? 0) || 0,
    productsWithInventory: Number(raw.products_with_inventory ?? raw.productsWithInventory ?? 0) || 0,
    warnings: Array.isArray(raw.warnings) ? raw.warnings : [],
  }
}

function mapInsightsPayload(data, stores = []) {
  const boundIds = new Set((stores || []).map((s) => s.id))
  const filterByStore = (items) =>
    (items || []).filter((item) => !boundIds.size || boundIds.has(item.storeId))

  return {
    products: filterByStore((data?.products || []).map(mapProduct).filter(isValidAmazonProduct)),
    outboundOrders: filterByStore((data?.outbound_orders || data?.outboundOrders || []).map(mapOutbound)),
    syncedAt: data?.synced_at ?? data?.syncedAt ?? '',
    dataQuality: mapDataQuality(data),
  }
}

export async function fetchAmazonDailyFromBackend(stores = []) {
  const res = await service.get('/api/amazon/daily', { skipGlobalErrorToast: true })
  const data = unwrapData(res)
  return { success: true, data: mapDailyPayload(data, stores) }
}

export async function fetchAmazonInsightsFromBackend(stores = []) {
  const res = await service.get('/api/amazon/insights', { skipGlobalErrorToast: true })
  const data = unwrapData(res)
  return { success: true, data: mapInsightsPayload(data, stores) }
}

export async function triggerAmazonSync(options = {}) {
  const crawlOpts = normalizeCrawlOptions(options)
  assertPlatformCrawlAllowed(null, crawlOpts)

  const body = {
    scope: options.scope || 'account_health',
  }
  if (options.platformAccountId) {
    body.platform_account_id = options.platformAccountId
  }
  applyCrawlRequestFlags(body, options)

  const token = getAccessToken()
  const res = await axios.post('/api/amazon/sync', body, {
    baseURL: import.meta.env.DEV ? '' : TEMU_API_BASE_URL,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    validateStatus: () => true,
    timeout: 120000,
  })

  const payload = res.data
  const data = unwrapData(payload)
  throwIfCrawlCooldownResponse(res, payload, '触发 Amazon 同步失败')
  if (res.status === 202 || payload?.code === 0 || payload?.success) {
    return { success: true, conflict: false, data }
  }
  if (res.status === 409 || payload?.code === 409) {
    return {
      success: true,
      conflict: true,
      data,
      message: getAppErrorMessage(payload?.error_code, payload?.msg || payload?.message),
    }
  }
  throw toAppApiError(payload, '触发 Amazon 同步失败')
}

export async function fetchAmazonSyncJob(jobId) {
  const res = await service.get(`/api/amazon/sync/${jobId}`, { skipGlobalErrorToast: true })
  return unwrapData(res)
}

function collectJobIds(started) {
  const data = started?.data || started || {}
  if (Array.isArray(data.jobs)) {
    return data.jobs.map((job) => job.job_id || job.jobId).filter(Boolean)
  }
  const single = data.job_id || data.jobId
  return single ? [single] : []
}

async function waitForJobs(jobIds, options = {}) {
  const pending = new Set(jobIds)
  const deadline = Date.now() + SYNC_MAX_WAIT_MS
  const outcomes = []

  while (pending.size && Date.now() < deadline) {
    for (const jobId of [...pending]) {
      const job = await fetchAmazonSyncJob(jobId)
      if (job.status === 'success' || job.status === 'partial') {
        outcomes.push(job)
        if (job.status === 'partial') {
          options.partial = true
          options.partialWarning = getAppErrorMessage(job.error_code, job.error_message)
          options.partialCode = job.error_code || 'AMAZON_NO_PRODUCT_ROWS'
        }
        pending.delete(jobId)
        continue
      }
      if (job.status === 'failed') {
        const err = new AppApiError(
          getAppErrorMessage(job.error_code, job.error_message || 'Amazon 数据同步失败'),
          job.error_code || 'AMAZON_SYNC_FAILED',
        )
        err.job = job
        throw err
      }
    }
    if (pending.size) {
      await sleep(SYNC_POLL_MS)
    }
  }

  if (pending.size) {
    throw new AppApiError(
      options.conflict
        ? '已有同步任务进行中，等待超时，请稍后再试'
        : 'Amazon 数据同步超时，请稍后重试',
      options.conflict ? 'AMAZON_SYNC_IN_PROGRESS' : 'CRAWL_TIMEOUT',
    )
  }
  return outcomes
}

async function refreshWithSync(stores, options, fetcher, message) {
  if (!isTemuBackendEnabled()) {
    throw new AppApiError('后端未启用', 'SERVER_ERROR')
  }

  const crawlOpts = normalizeCrawlOptions(options)

  const started = await triggerAmazonSync(options)
  const jobIds = collectJobIds(started)
  if (!jobIds.length) {
    throw new AppApiError('未获取到 Amazon 同步任务 ID', 'AMAZON_SYNC_FAILED')
  }

  const waitOptions = { conflict: started.conflict }
  const outcomes = await waitForJobs(jobIds, waitOptions)
  const res = await fetcher(stores)
  const lastJob = outcomes[outcomes.length - 1] || null
  const resultSummary = lastJob?.result_summary || lastJob?.resultSummary || {}
  const result = {
    success: true,
    partial: Boolean(waitOptions.partial),
    warning: waitOptions.partialWarning || '',
    errorCode: waitOptions.partialCode || lastJob?.error_code || '',
    errorMessage: lastJob?.error_message || '',
    resultSummary,
    job: lastJob,
    message: waitOptions.partial
      ? (waitOptions.partialWarning || '同步完成，但产品数据为空')
      : (started.conflict ? '已等待进行中的同步任务完成' : message),
    data: res.data,
  }
  markPlatformCrawlOnSuccess(null, result, { enabled: crawlOpts.recordCooldown })
  return result
}

export async function refreshAmazonDailyWithSync(stores = [], options = {}) {
  return refreshWithSync(
    stores,
    { scope: options.scope || 'daily', platformAccountId: options.platformAccountId },
    fetchAmazonDailyFromBackend,
    options.scope === 'account_health' ? '已刷新账户状况数据' : '已刷新今日运营数据',
  )
}

export async function refreshAmazonInsightsWithSync(stores = [], options = {}) {
  return refreshWithSync(
    stores,
    { scope: 'insights', platformAccountId: options.platformAccountId },
    fetchAmazonInsightsFromBackend,
    '已刷新产品与订单数据',
  )
}

export async function refreshAmazonReportsWithSync(stores = [], options = {}) {
  return refreshWithSync(
    stores,
    { scope: 'reports', platformAccountId: options.platformAccountId },
    fetchAmazonInsightsFromBackend,
    '已刷新 Business Report 产品数据',
  )
}

export async function refreshAmazonAllWithSync(stores = [], options = {}) {
  const innerOpts = {
    ...options,
    [PLATFORM_SYNC_BATCH_GUARD]: true,
    recordCooldown: false,
  }
  // Amazon tasks for the same bound browser are mutually exclusive. Running
  // these ranges in parallel makes the second request wait on the first job
  // instead of collecting its own scope.
  const settle = async (operation) => {
    try {
      return { status: 'fulfilled', value: await operation() }
    } catch (reason) {
      return { status: 'rejected', reason }
    }
  }
  const dailyResult = await settle(() =>
    refreshWithSync(
      stores,
      { scope: 'daily', platformAccountId: options.platformAccountId, ...innerOpts },
      fetchAmazonDailyFromBackend,
      '已刷新今日运营数据',
    ),
  )
  const reportsResult = await settle(() =>
    refreshWithSync(
      stores,
      { scope: 'reports', platformAccountId: options.platformAccountId, ...innerOpts },
      fetchAmazonInsightsFromBackend,
      '已刷新 Business Report 产品数据',
    ),
  )

  const errors = [dailyResult, reportsResult]
    .filter((item) => item.status === 'rejected')
    .map((item) => item.reason?.message || '同步失败')

  if (errors.length === 2) {
    throw errors[0] instanceof AppApiError
      ? errors[0]
      : new AppApiError(errors[0], 'AMAZON_SYNC_FAILED')
  }

  const dailyData = dailyResult.status === 'fulfilled' ? dailyResult.value.data : null
  const insightsData = reportsResult.status === 'fulfilled' ? reportsResult.value.data : null
  const job = (dailyResult.status === 'fulfilled' && dailyResult.value.job)
    || (reportsResult.status === 'fulfilled' && reportsResult.value.job)
    || null
  const partial = [dailyResult, reportsResult].some(
    (item) => item.status === 'fulfilled' && item.value.partial,
  ) || errors.length > 0
  const warning = [dailyResult, reportsResult]
    .filter((item) => item.status === 'fulfilled' && item.value.partial)
    .map((item) => item.value.warning)
    .find(Boolean)

  const result = {
    success: true,
    partial,
    warning,
    job,
    message: errors.length
      ? `部分同步完成：${errors[0]}`
      : (partial ? warning : '已刷新 Amazon 全部数据'),
    toastType: errors.length || partial ? 'warning' : 'success',
    data: {
      daily: dailyData,
      insights: insightsData,
    },
    dailyData,
    insightsData,
  }
  markPlatformCrawlOnSuccess(null, result, {
    enabled: options.recordCooldown ?? !isPlatformSyncBatchOptions(options),
  })
  return result
}

export async function fetchAmazonSpApiStatus() {
  const res = await service.get('/api/amazon/sp-api/status', { skipGlobalErrorToast: true })
  return { success: true, data: unwrapData(res) }
}

export async function fetchAmazonSyncJobs({ limit = 20 } = {}) {
  const res = await service.get('/api/amazon/sync-jobs', { params: { limit }, skipGlobalErrorToast: true })
  const body = unwrapData(res) || {}
  return Array.isArray(body.items) ? body.items : []
}

const WRITE_POLL_MS = 2000
const WRITE_MAX_WAIT_MS = 180000

async function waitForAmazonWriteJob(jobId) {
  const deadline = Date.now() + WRITE_MAX_WAIT_MS
  while (Date.now() < deadline) {
    const job = unwrapData(await service.get(`/api/amazon/write/${jobId}`, { skipGlobalErrorToast: true }))
    if (job.status === 'success') {
      return job
    }
    if (job.status === 'failed') {
      throw new AppApiError(
        getAppErrorMessage(job.error_code, job.error_message || 'Amazon 写操作失败'),
        job.error_code || 'AMAZON_WRITE_FAILED',
      )
    }
    await sleep(WRITE_POLL_MS)
  }
  throw new AppApiError('Amazon 写操作超时，请稍后在 Seller Central 确认', 'CRAWL_TIMEOUT')
}

async function patchAmazonWrite(path, body, mapper) {
  const res = await service.patch(path, body)
  const data = unwrapData(res)
  const jobId = data.write_job_id || data.writeJobId
  if (jobId && (data.write_status === 'pending' || data.status === 'pending_write')) {
    await waitForAmazonWriteJob(jobId)
  }
  return { success: true, data: mapper(data) }
}

export async function replyAmazonMessageBackend(id, payload = {}) {
  return patchAmazonWrite(`/api/amazon/daily/messages/${id}`, {
    template_id: payload.templateId,
    note: payload.note || '',
  }, mapMessage)
}

export async function handleAmazonReviewBackend(id, payload = {}) {
  return patchAmazonWrite(`/api/amazon/daily/reviews/${id}`, {
    note: payload.note || '',
  }, mapReview)
}

export async function acknowledgeAmazonCaseBackend(id) {
  return patchAmazonWrite(`/api/amazon/daily/cases/${id}`, {}, mapCase)
}

export async function shipAmazonOutboundBackend(id, payload = {}) {
  return patchAmazonWrite(`/api/amazon/outbound/${id}/ship`, {
    tracking_no: payload.trackingNo || '',
  }, mapOutbound)
}

export async function submitAmazonChat({ storeId, sessionId = '', message }) {
  const res = await service.post('/api/amazon/chat', {
    store_id: storeId,
    session_id: sessionId,
    message,
  })
  return unwrapData(res)
}

export async function fetchAmazonChatJob(jobId) {
  const res = await service.get(`/api/amazon/chat/jobs/${jobId}`, { skipGlobalErrorToast: true })
  return unwrapData(res)
}

export async function fetchAmazonChatSessions({ storeId = '', limit = 20 } = {}) {
  const res = await service.get('/api/amazon/chat/sessions', {
    params: { store_id: storeId, limit },
    skipGlobalErrorToast: true,
  })
  return unwrapData(res)
}

export async function fetchAmazonChatMessages(sessionId) {
  const res = await service.get(`/api/amazon/chat/sessions/${sessionId}/messages`, {
    skipGlobalErrorToast: true,
  })
  return unwrapData(res)
}

export async function fetchAmazonChatMemory(storeId) {
  const res = await service.get(`/api/amazon/chat/memory/${storeId}`, { skipGlobalErrorToast: true })
  return unwrapData(res)
}

export async function clearAmazonChatMemory(storeId) {
  const res = await service.delete(`/api/amazon/chat/memory/${storeId}`)
  return unwrapData(res)
}

export function canUseAmazonBackend() {
  return isBackendLinked() && isTemuBackendEnabled()
}
