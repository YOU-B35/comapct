import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { loadScoped, resolveTenantId, saveScoped } from '@/utils/tenantStorage'
import { WALMART_LISTING_ISSUES_SEED } from '@/constants/walmartDemo'

const STORAGE_KEY = 'crosshub_walmart_listings'

const EMPTY = { syncedAt: '', items: [] }

function nowText() {
  return nowUtc8String()
}

function loadState(tenantId = resolveTenantId()) {
  return loadScoped(tenantId, STORAGE_KEY, EMPTY) || { ...EMPTY }
}

function saveState(state, tenantId = resolveTenantId()) {
  saveScoped(tenantId, STORAGE_KEY, state)
}

function ensureIssuesForStores(stores) {
  const state = loadState()
  const storeIds = new Set(stores.map((s) => s.id))
  let items = [...state.items]

  for (const seed of WALMART_LISTING_ISSUES_SEED) {
    if (!storeIds.has(seed.storeId)) continue
    if (!items.some((row) => row.id === seed.id)) {
      items.push({ ...seed })
    }
  }

  items = items.filter((item) => storeIds.has(item.storeId))
  const next = { syncedAt: state.syncedAt || nowText(), items }
  saveState(next)
  return next
}

export function fetchWalmartListingIssues(stores) {
  const state = ensureIssuesForStores(stores)
  return {
    success: true,
    data: {
      issues: state.items,
      syncedAt: state.syncedAt,
    },
  }
}

export function syncWalmartListingIssues(stores, options = {}) {
  const state = ensureIssuesForStores(stores)
  if (options.refresh) {
    state.syncedAt = nowText()
    saveState(state)
  }
  return {
    success: true,
    message: options.refresh ? '已刷新 Walmart Listing 问题' : undefined,
    data: {
      issues: state.items,
      syncedAt: state.syncedAt,
    },
  }
}

export function resolveWalmartListingIssue(id, payload = {}) {
  const state = loadState()
  const index = state.items.findIndex((item) => item.id === id)
  if (index === -1) throw new Error('问题不存在')

  state.items[index] = {
    ...state.items[index],
    resolved: payload.resolved !== false,
    resolveNote: payload.note || '',
    resolvedAt: nowText(),
  }
  saveState(state)
  return { success: true, data: state.items[index] }
}
