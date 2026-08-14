import {
  pddOrdersLocal,
  pddIssuesLocal,
  douyinOrdersLocal,
  douyinIssuesLocal,
  channelsOrdersLocal,
  channelsIssuesLocal,
} from './domesticStoresLocal'
import {
  canUseDouyinBackend,
  syncDouyinOrdersToday,
  fetchDouyinOrdersToday,
  fetchDouyinIssues,
  syncDouyinIssues,
  resolveDouyinIssueApi,
} from './douyinApi'
import { useAuthStore } from '@/stores/auth'

function authForBackend() {
  try {
    return useAuthStore()
  } catch {
    return null
  }
}

export async function fetchTodayPddOrders(stores, options = {}) {
  return pddOrdersLocal.syncTodayOrders(stores, options)
}

export function loadCachedPddOrders(stores) {
  return pddOrdersLocal.fetchCachedOrders(stores)
}

export function loadPddIssues(stores) {
  return pddIssuesLocal.fetchIssues(stores)
}

export async function crawlPddIssues(stores, options = {}) {
  return pddIssuesLocal.syncIssues(stores, options)
}

export function resolvePddIssue(id, payload) {
  return pddIssuesLocal.resolveIssue(id, payload)
}

export async function fetchTodayDouyinOrders(stores, options = {}) {
  const auth = authForBackend()
  if (canUseDouyinBackend(auth)) {
    return syncDouyinOrdersToday(stores, options)
  }
  return douyinOrdersLocal.syncTodayOrders(stores, options)
}

export function loadCachedDouyinOrders(stores) {
  const auth = authForBackend()
  if (canUseDouyinBackend(auth)) {
    return { items: [], syncedAt: '' }
  }
  return douyinOrdersLocal.fetchCachedOrders(stores)
}

export async function loadDouyinIssues(stores, options = {}) {
  const auth = authForBackend()
  if (canUseDouyinBackend(auth)) {
    const storeId = options.storeId || null
    const data = await fetchDouyinIssues({ storeId })
    return {
      success: true,
      data: {
        issues: data.items || [],
        syncedAt: data.synced_at || '',
      },
    }
  }
  return douyinIssuesLocal.fetchIssues(stores)
}

export async function crawlDouyinIssues(stores, options = {}) {
  const auth = authForBackend()
  if (canUseDouyinBackend(auth)) {
    return syncDouyinIssues({
      force: options.force !== false,
      storeId: options.storeId || null,
      refresh: options.refresh !== false,
    })
  }
  return douyinIssuesLocal.syncIssues(stores, options)
}

export async function resolveDouyinIssue(id, payload) {
  const auth = authForBackend()
  if (canUseDouyinBackend(auth)) {
    return resolveDouyinIssueApi(id, payload)
  }
  return douyinIssuesLocal.resolveIssue(id, payload)
}

export async function fetchTodayChannelsOrders(stores, options = {}) {
  return channelsOrdersLocal.syncTodayOrders(stores, options)
}

export function loadCachedChannelsOrders(stores) {
  return channelsOrdersLocal.fetchCachedOrders(stores)
}

export function loadChannelsIssues(stores) {
  return channelsIssuesLocal.fetchIssues(stores)
}

export async function crawlChannelsIssues(stores, options = {}) {
  return channelsIssuesLocal.syncIssues(stores, options)
}

export function resolveChannelsIssue(id, payload) {
  return channelsIssuesLocal.resolveIssue(id, payload)
}

export { fetchDouyinOrdersToday }
