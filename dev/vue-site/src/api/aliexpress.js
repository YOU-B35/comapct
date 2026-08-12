import {
  canUseAliExpressBackend,
  loadAliExpressModuleData,
  fetchTodayAliExpressOrdersFromApi,
  loadAliExpressViolationsFromApi,
  crawlAliExpressViolationsFromApi,
  confirmAliExpressViolationAppealFromApi,
  fetchAliexpressDemoData,
  syncTodayAliExpressOrders,
  fetchCachedAliExpressOrders,
  loadStoredViolations,
  syncAliExpressViolations,
  confirmViolationAppeal,
} from './aliexpressApi'

export function loadAliExpressOperationalData(stores, auth) {
  if (canUseAliExpressBackend(auth)) {
    return loadAliExpressModuleData({ auth, stores })
  }
  return fetchAliexpressDemoData(stores)
}

export async function fetchTodayAliExpressOrders(stores, options = {}) {
  const { auth, refresh = false, storeId, ...crawlOptions } = options
  if (canUseAliExpressBackend(auth)) {
    const data = await fetchTodayAliExpressOrdersFromApi({ storeId, refresh, ...crawlOptions })
    return {
      data: {
        orders: data.orders,
        syncedAt: data.syncedAt,
      },
      job: data.job || null,
      message: refresh ? (data.message || `已同步 ${data.orders.length} 笔今日订单`) : '',
    }
  }
  const demoRes = fetchAliexpressDemoData(stores)
  return syncTodayAliExpressOrders(stores, demoRes.data.products, { refresh })
}

export function loadCachedAliExpressOrders(stores, auth) {
  if (canUseAliExpressBackend(auth)) {
    return { data: { orders: [], syncedAt: '' } }
  }
  return fetchCachedAliExpressOrders(stores)
}

export function loadAliExpressViolations(stores, auth, options = {}) {
  if (canUseAliExpressBackend(auth)) {
    return loadAliExpressViolationsFromApi({ storeId: options.storeId })
      .then((data) => ({
        data: {
          violations: data.violations,
          syncedAt: data.syncedAt,
        },
      }))
  }
  return Promise.resolve({
    data: loadStoredViolations(stores).data,
  })
}

export async function crawlAliExpressViolations(stores, options = {}) {
  const { auth, refresh = false } = options
  if (canUseAliExpressBackend(auth)) {
    if (!refresh) {
      const cached = await loadAliExpressViolationsFromApi()
      return {
        data: cached,
        message: '',
      }
    }
    const data = await crawlAliExpressViolationsFromApi(options)
    return {
      data,
      job: data.job || null,
      message: `已同步 ${data.violations.length} 条违规记录`,
    }
  }
  return syncAliExpressViolations(stores, { refresh })
}

export function confirmAliExpressViolationAppeal(id, payload, auth) {
  if (canUseAliExpressBackend(auth)) {
    return confirmAliExpressViolationAppealFromApi(id, payload).then((res) => ({
      data: res,
    }))
  }
  return confirmViolationAppeal(id, payload)
}
