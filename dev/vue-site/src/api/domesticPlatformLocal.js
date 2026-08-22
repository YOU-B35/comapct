import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { DOMESTIC_ORDER_STATUSES } from '@/constants/domesticShared'
import { loadScoped, resolveTenantId, saveScoped } from '@/utils/tenantStorage'

function todayKey() {
  return nowUtc8DateString()
}

function nowText() {
  return nowUtc8String()
}

function hashStoreId(id) {
  let hash = 0
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0
  }
  return hash
}

function pick(list, storeId, index) {
  return list[hashStoreId(`${storeId}_${index}`) % list.length]
}

function buildTimeToday(hour, minute) {
  return `${todayKey()} ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00`
}

export function createDomesticOrdersLocal(config) {
  const {
    storageKey,
    seedOrders,
    orderPrefix,
    refreshMessage,
    channels = ['商城'],
  } = config

  function loadState() {
    const tenantId = resolveTenantId()
    return loadScoped(tenantId, storageKey, { date: '', syncedAt: '', items: [] })
      || { date: '', syncedAt: '', items: [] }
  }

  function saveState(state) {
    saveScoped(resolveTenantId(), storageKey, state)
  }

  function normalizeSeedOrders() {
    const date = todayKey()
    return seedOrders.map((order) => ({
      ...order,
      orderedAt: order.orderedAt.replace(/^\d{4}-\d{2}-\d{2}/, date),
      shipDeadline: order.shipDeadline
        ? order.shipDeadline.replace(/^\d{4}-\d{2}-\d{2}/, date)
        : null,
    }))
  }

  function generateOrdersForStore(store) {
    const products = [
      { sku: `${orderPrefix}-${store.id.slice(-4)}-A`, name: '户外折叠椅' },
      { sku: `${orderPrefix}-${store.id.slice(-4)}-B`, name: '便携露营灯' },
      { sku: `${orderPrefix}-${store.id.slice(-4)}-C`, name: '防水收纳包' },
    ]
    const count = 2 + (hashStoreId(store.id) % 2)
    const orders = []

    for (let i = 0; i < count; i += 1) {
      const product = products[i % products.length]
      orders.push({
        id: `${orderPrefix.toLowerCase()}_order_${store.id}_${i + 1}`,
        orderNo: `${orderPrefix}${String(hashStoreId(`${store.id}_${i}`)).padStart(11, '0')}`,
        storeId: store.id,
        sku: product.sku,
        productName: product.name,
        quantity: 1 + (i % 2),
        amount: Number((59.9 + i * 20).toFixed(2)),
        currency: 'CNY',
        channel: pick(channels, store.id, i),
        status: pick(DOMESTIC_ORDER_STATUSES.slice(0, 3), store.id, i),
        orderedAt: buildTimeToday(7 + i * 2, 20),
        shipDeadline: `${todayKey()} 18:00:00`,
      })
    }

    return orders
  }

  function ensureOrdersForStores(stores) {
    const date = todayKey()
    const state = loadState()
    const seedItems = normalizeSeedOrders()
    const storeIds = new Set(stores.map((s) => s.id))

    let items = state.date === date ? [...state.items] : []
    if (state.date !== date) {
      items = seedItems.filter((o) => storeIds.has(o.storeId))
    }

    for (const store of stores) {
      if (items.some((o) => o.storeId === store.id)) continue
      items.push(...generateOrdersForStore(store))
    }

    items = items.filter((o) => storeIds.has(o.storeId))
    const next = { date, syncedAt: state.syncedAt || nowText(), items }
    saveState(next)
    return next
  }

  function syncTodayOrders(stores, options = {}) {
    const state = ensureOrdersForStores(stores)
    if (options.refresh) {
      const generated = stores.flatMap((store) => generateOrdersForStore(store))
      const seedItems = normalizeSeedOrders().filter((o) =>
        stores.some((s) => s.id === o.storeId),
      )
      const byId = new Map([...seedItems, ...generated].map((o) => [o.id, o]))
      state.items = Array.from(byId.values())
      state.syncedAt = nowText()
      saveState(state)
    }
    return {
      success: true,
      message: options.refresh ? refreshMessage : undefined,
      data: {
        orders: state.items,
        syncedAt: state.syncedAt,
      },
    }
  }

  function fetchCachedOrders(stores) {
    const state = ensureOrdersForStores(stores)
    return {
      success: true,
      data: {
        orders: state.items,
        syncedAt: state.syncedAt,
      },
    }
  }

  return { syncTodayOrders, fetchCachedOrders }
}

export function createDomesticIssuesLocal(config) {
  const { storageKey, seedIssues, refreshMessage } = config

  function loadState() {
    const tenantId = resolveTenantId()
    return loadScoped(tenantId, storageKey, { syncedAt: '', items: [] })
      || { syncedAt: '', items: [] }
  }

  function saveState(state) {
    saveScoped(resolveTenantId(), storageKey, state)
  }

  function ensureIssuesForStores(stores) {
    const state = loadState()
    const storeIds = new Set(stores.map((s) => s.id))
    let items = [...state.items]

    for (const seed of seedIssues) {
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

  function fetchIssues(stores) {
    const state = ensureIssuesForStores(stores)
    return {
      success: true,
      data: {
        issues: state.items,
        syncedAt: state.syncedAt,
      },
    }
  }

  function syncIssues(stores, options = {}) {
    const state = ensureIssuesForStores(stores)
    if (options.refresh) {
      state.syncedAt = nowText()
      saveState(state)
    }
    return {
      success: true,
      message: options.refresh ? refreshMessage : undefined,
      data: {
        issues: state.items,
        syncedAt: state.syncedAt,
      },
    }
  }

  function resolveIssue(id, payload = {}) {
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

  return { fetchIssues, syncIssues, resolveIssue }
}
