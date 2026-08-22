import {
  pddOrdersLocal,
  pddIssuesLocal,
  douyinOrdersLocal,
  douyinIssuesLocal,
  channelsOrdersLocal,
  channelsIssuesLocal,
  taobaoOrdersLocal,
  taobaoIssuesLocal,
} from './domesticStoresLocal'
import {
  canUseDouyinBackend,
  syncDouyinOrdersToday,
  fetchDouyinOrdersToday,
  fetchDouyinIssues,
  syncDouyinIssues,
  resolveDouyinIssueApi,
} from './douyinApi'
import {
  canUsePddBackend,
  syncPddOrdersToday,
  fetchPddIssues,
  syncPddIssues,
  resolvePddIssueApi,
} from './pddApi'
import {
  canUseTaobaoBackend,
  syncTaobaoOrdersToday,
  fetchTaobaoIssues,
  syncTaobaoIssues,
  resolveTaobaoIssueApi,
} from './taobaoApi'
import { useAuthStore } from '@/stores/auth'

function authForBackend() {
  try {
    return useAuthStore()
  } catch {
    return null
  }
}

export async function fetchTodayPddOrders(stores, options = {}) {
  const auth = authForBackend()
  if (canUsePddBackend(auth)) {
    return syncPddOrdersToday(stores, options)
  }
  return pddOrdersLocal.syncTodayOrders(stores, options)
}

export function loadCachedPddOrders(stores) {
  const auth = authForBackend()
  if (canUsePddBackend(auth)) {
    return { items: [], syncedAt: '' }
  }
  return pddOrdersLocal.fetchCachedOrders(stores)
}

export async function loadPddIssues(stores, options = {}) {
  const auth = authForBackend()
  if (canUsePddBackend(auth)) {
    const storeId = options.storeId || null
    const data = await fetchPddIssues({ storeId })
    return {
      success: true,
      data: {
        issues: data.items || [],
        syncedAt: data.synced_at || '',
      },
    }
  }
  return pddIssuesLocal.fetchIssues(stores)
}

export async function crawlPddIssues(stores, options = {}) {
  const auth = authForBackend()
  if (canUsePddBackend(auth)) {
    return syncPddIssues({
      force: options.force !== false,
      storeId: options.storeId || null,
      refresh: options.refresh !== false,
    })
  }
  return pddIssuesLocal.syncIssues(stores, options)
}

export async function resolvePddIssue(id, payload) {
  const auth = authForBackend()
  if (canUsePddBackend(auth)) {
    return resolvePddIssueApi(id, payload)
  }
  return pddIssuesLocal.resolveIssue(id, payload)
}

export async function fetchTodayTaobaoOrders(stores, options = {}) {
  const auth = authForBackend()
  if (canUseTaobaoBackend(auth)) {
    return syncTaobaoOrdersToday(stores, options)
  }
  return taobaoOrdersLocal.syncTodayOrders(stores, options)
}

export function loadCachedTaobaoOrders(stores) {
  const auth = authForBackend()
  if (canUseTaobaoBackend(auth)) {
    return { items: [], syncedAt: '' }
  }
  return taobaoOrdersLocal.fetchCachedOrders(stores)
}

export async function loadTaobaoIssues(stores, options = {}) {
  const auth = authForBackend()
  if (canUseTaobaoBackend(auth)) {
    const storeId = options.storeId || null
    const data = await fetchTaobaoIssues({ storeId })
    return {
      success: true,
      data: {
        issues: data.items || [],
        syncedAt: data.synced_at || '',
      },
    }
  }
  return taobaoIssuesLocal.fetchIssues(stores)
}

export async function crawlTaobaoIssues(stores, options = {}) {
  const auth = authForBackend()
  if (canUseTaobaoBackend(auth)) {
    return syncTaobaoIssues({
      force: options.force !== false,
      storeId: options.storeId || null,
      refresh: options.refresh !== false,
    })
  }
  return taobaoIssuesLocal.syncIssues(stores, options)
}

export async function resolveTaobaoIssue(id, payload) {
  const auth = authForBackend()
  if (canUseTaobaoBackend(auth)) {
    return resolveTaobaoIssueApi(id, payload)
  }
  return taobaoIssuesLocal.resolveIssue(id, payload)
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
