import { formatUtc8 } from './time.js'

function parseSyncTimestamp(value) {
  const raw = String(value || '').trim()
  if (!raw) return null
  // Accept "YYYY-MM-DD HH:mm:ss" by normalizing to ISO-ish
  const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T')
  const ms = Date.parse(normalized)
  return Number.isFinite(ms) ? ms : null
}

export function formatSyncDuration(startedAt, finishedAt) {
  const a = parseSyncTimestamp(startedAt)
  const b = parseSyncTimestamp(finishedAt)
  if (a == null || b == null || b < a) return '—'
  const sec = Math.round((b - a) / 1000)
  if (sec < 60) return `${sec}秒`
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return s ? `${m}分${s}秒` : `${m}分`
}

export function formatSyncClock(isoLike) {
  const s = formatUtc8(isoLike, { seconds: false })
  return s === '—' ? '' : s
}

export function formatTriggerLabel(job = {}) {
  const trigger = String(job.trigger || '').toLowerCase()
  if (trigger === 'daily_schedule' || trigger === 'daily' || trigger === '定时') return '定时'
  if (job.triggered_by === 0 || job.triggered_by === '0') return '定时'
  return '手动'
}

export function formatRecordCount(job = {}, platform = '') {
  const p = String(platform || '').toLowerCase()
  if (p === 'temu') {
    const rows = Number(job.rows_count ?? job.rowsCount ?? 0) || 0
    const shops = Number(job.shops_count ?? job.shopsCount ?? 0) || 0
    return shops > 0 ? `${rows} 条 · ${shops} 店` : `${rows} 条`
  }
  if (p === 'aliexpress') {
    const parts = []
    const orders = job.orders_count ?? job.ordersCount
    const products = job.products_count ?? job.productsCount
    const violations = job.violations_count ?? job.violationsCount
    const rows = job.rows_count ?? job.rowsCount
    if (orders != null) parts.push(`${Number(orders) || 0} 订单`)
    if (products != null) parts.push(`${Number(products) || 0} 商品`)
    if (violations != null) parts.push(`${Number(violations) || 0} 违规`)
    if (!parts.length && rows != null) parts.push(`${Number(rows) || 0} 条`)
    return parts.join(' · ') || '0 条'
  }
  // pdd / douyin / 1688 / taobao：订单、商品、售后/预警、罗盘等分平台口径
  if (['pdd', 'douyin', '1688', 'alibaba1688', 'taobao', 'issues'].includes(p)) {
    const parts = []
    const orders = job.orders_count ?? job.ordersCount
    const products = job.products_count ?? job.productsCount
    const issues = job.issues_count ?? job.issuesCount
    const compass = job.compass_count ?? job.compassCount
    const peers = job.peer_bestsellers_count ?? job.peerBestsellersCount
    if (orders != null) parts.push(`${Number(orders) || 0} 订单`)
    if (products != null) parts.push(`${Number(products) || 0} 商品`)
    if (issues != null) parts.push(`${Number(issues) || 0} 预警`)
    if (compass != null) parts.push(`${Number(compass) || 0} 罗盘`)
    if (peers != null) parts.push(`${Number(peers) || 0} 同行`)
    if (parts.length) return parts.join(' · ')
  }
  // 兜底：通用行数
  const genericRows = job.rows_count ?? job.rowsCount
  if (genericRows != null) return `${Number(genericRows) || 0} 条`
  // amazon
  const products = job.products_count ?? job.product_count ?? job.productsCount
  const items = job.item_count ?? job.items_count ?? job.itemCount
  const metrics = job.metric_count ?? job.metrics_count
  const parts = []
  if (products != null) parts.push(`${Number(products) || 0} 商品`)
  if (items != null) parts.push(`${Number(items) || 0} 事项`)
  if (metrics != null) parts.push(`${Number(metrics) || 0} 指标`)
  if (!parts.length) {
    const rows = job.rows_count ?? job.rowsCount
    if (rows != null) return `${Number(rows) || 0} 条`
  }
  return parts.join(' · ') || '—'
}

export function buildSyncSummaryText(job, platform) {
  if (!job) return '尚未同步'
  const status = String(job.status || '').toLowerCase()
  if (['running', 'pending', 'retry_wait', 'queued'].includes(status)) return '同步中…'
  const clockSrc = job.finished_at || job.finishedAt || job.started_at || job.startedAt || job.created_at || job.createdAt || ''
  const clock = formatSyncClock(clockSrc)
  if (['failed', 'error'].includes(status)) {
    const err = String(job.error_message || job.errorMessage || job.failure_reason || '').trim()
    const short = err ? err.slice(0, 40) : '同步失败'
    return clock ? `最近同步失败 ${clock} · ${short}` : `最近同步失败 · ${short}`
  }
  if (!clock) return '尚未同步'
  const count = formatRecordCount(job, platform)
  const dur = formatSyncDuration(
    job.started_at || job.startedAt || '',
    job.finished_at || job.finishedAt || '',
  )
  const durPart = dur === '—' ? '' : ` · 耗时 ${dur}`
  return `最近同步 ${clock} · ${count}${durPart}`
}

export function normalizeSyncJob(raw = {}) {
  return {
    label: raw.label || raw.task_type || '',
    job_id: raw.job_id || raw.id || '',
    status: raw.status || '',
    started_at: raw.started_at || raw.startedAt || '',
    finished_at: raw.finished_at || raw.finishedAt || '',
    created_at: raw.created_at || raw.createdAt || '',
    rows_count: raw.rows_count ?? raw.rowsCount ?? null,
    shops_count: raw.shops_count ?? raw.shopsCount ?? null,
    orders_count: raw.orders_count ?? raw.ordersCount ?? null,
    products_count: raw.products_count ?? raw.product_count ?? raw.productsCount ?? null,
    violations_count: raw.violations_count ?? raw.violationsCount ?? null,
    compass_count: raw.compass_count ?? raw.compassCount ?? null,
    peer_bestsellers_count: raw.peer_bestsellers_count ?? raw.peerBestsellersCount ?? null,
    item_count: raw.item_count ?? raw.itemCount ?? null,
    metric_count: raw.metric_count ?? raw.metricCount ?? null,
    rows_count: raw.rows_count ?? raw.rowsCount ?? null,
    summary: raw.summary || raw.message || '',
    triggered_by: raw.triggered_by ?? raw.triggeredBy ?? null,
    trigger: raw.trigger || '',
    error_code: raw.error_code || raw.errorCode || raw.failure_code || '',
    error_message: raw.error_message || raw.errorMessage || raw.failure_reason || '',
  }
}
