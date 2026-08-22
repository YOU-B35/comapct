import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { OPS_FEEDBACK_SEED, OUTCOME_MAP } from '@/constants/opsFeedbackDemo'
import { loadScoped, resolveTenantId, saveScoped, isDemoTemplateEnabled } from '@/utils/tenantStorage'

const STORAGE_KEY = 'crosshub_ops_feedback'
const SEED_FLAG_KEY = 'crosshub_ops_feedback_seeded'

function todayKey() {
  return nowUtc8DateString()
}

function nowText() {
  return nowUtc8String()
}

function loadAll(tenantId = resolveTenantId()) {
  return loadScoped(tenantId, STORAGE_KEY, []) || []
}

function saveAll(items, tenantId = resolveTenantId()) {
  saveScoped(tenantId, STORAGE_KEY, items)
}

function ensureSeedFeedback(tenantId = resolveTenantId()) {
  if (!isDemoTemplateEnabled(tenantId)) return
  if (loadScoped(tenantId, SEED_FLAG_KEY)) return
  const date = todayKey()
  const seeded = OPS_FEEDBACK_SEED.map((item) => ({
    ...item,
    date: item.date || date,
  }))
  const existing = loadAll(tenantId)
  const ids = new Set(existing.map((item) => item.id))
  const merged = [...existing, ...seeded.filter((item) => !ids.has(item.id))]
  saveAll(merged, tenantId)
  saveScoped(tenantId, SEED_FLAG_KEY, '1')
}

export function fetchOpsFeedback(options = {}) {
  ensureSeedFeedback()
  let items = loadAll()
  const date = options.date || todayKey()

  if (options.date !== 'all') {
    items = items.filter((item) => item.date === date)
  }

  if (options.employeeId) {
    items = items.filter((item) => item.employeeId === options.employeeId)
  }

  return items.sort((a, b) => String(b.submittedAt).localeCompare(String(a.submittedAt)))
}

export function submitOpsFeedback(payload) {
  ensureSeedFeedback()
  const items = loadAll()
  const outcome = OUTCOME_MAP[payload.outcome] || OUTCOME_MAP.in_progress

  const row = {
    id: `fb_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    taskId: payload.taskId,
    employeeId: payload.employeeId,
    employeeName: payload.employeeName,
    employeeRole: payload.employeeRole || '',
    platform: payload.platform,
    platformKey: payload.platformKey,
    taskTitle: payload.taskTitle,
    category: payload.category || '',
    outcome: payload.outcome || 'in_progress',
    outcomeLabel: outcome.label,
    feedback: (payload.feedback || '').trim(),
    storeName: payload.storeName || '—',
    date: todayKey(),
    submittedAt: nowText(),
  }

  items.unshift(row)
  saveAll(items)
  return { success: true, data: row }
}

export function getFeedbackByTaskId(taskId) {
  return fetchOpsFeedback({ date: 'all' }).find((item) => item.taskId === taskId)
}

export function fetchFeedbacksByTaskId(taskId) {
  return fetchOpsFeedback({ date: 'all' })
    .filter((item) => item.taskId === taskId)
    .sort((a, b) => String(b.submittedAt).localeCompare(String(a.submittedAt)))
}
