import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { loadScoped, resolveTenantId, saveScoped } from '@/utils/tenantStorage'
import { WALMART_ORDERS_SEED, WFS_ORDER_STATUSES, SELLER_ORDER_STATUSES } from '@/constants/walmartDemo'

const STORAGE_KEY = 'crosshub_walmart_orders'

const EMPTY = { date: '', syncedAt: '', items: [] }

function todayKey() {
  return nowUtc8DateString()
}

function nowText() {
  return nowUtc8String()
}

function loadState(tenantId = resolveTenantId()) {
  return loadScoped(tenantId, STORAGE_KEY, EMPTY) || { ...EMPTY }
}

function saveState(state, tenantId = resolveTenantId()) {
  saveScoped(tenantId, STORAGE_KEY, state)
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

function normalizeSeedOrders() {
  const date = todayKey()
  return WALMART_ORDERS_SEED.map((order) => ({
    ...order,
    orderedAt: order.orderedAt.replace(/^\d{4}-\d{2}-\d{2}/, date),
    shipDeadline: order.shipDeadline
      ? order.shipDeadline.replace(/^\d{4}-\d{2}-\d{2}/, date)
      : null,
  }))
}

function generateOrdersForStore(store) {
  const products = [
    { sku: `WM-${store.id.slice(-4)}-A`, name: '户外折叠椅' },
    { sku: `WM-${store.id.slice(-4)}-B`, name: '便携露营灯' },
    { sku: `WM-${store.id.slice(-4)}-C`, name: '防水收纳包' },
  ]
  const orders = []
  const wfsCount = 2 + (hashStoreId(store.id) % 2)

  for (let i = 0; i < wfsCount; i += 1) {
    const product = products[i % products.length]
    orders.push({
      id: `wm_order_wfs_${store.id}_${i + 1}`,
      orderNo: `WM${String(hashStoreId(`${store.id}_w${i}`)).padStart(11, '0')}`,
      storeId: store.id,
      fulfillmentType: 'wfs',
      sku: product.sku,
      productName: product.name,
      quantity: 1 + (i % 2),
      amount: Number((39.99 + i * 10).toFixed(2)),
      currency: 'USD',
      status: pick(WFS_ORDER_STATUSES.slice(0, 3), store.id, i),
      orderedAt: buildTimeToday(7 + i * 2, 15),
      shipDeadline: `${todayKey()} 18:00:00`,
    })
  }

  orders.push({
    id: `wm_order_seller_${store.id}_1`,
    orderNo: `WM${String(hashStoreId(`${store.id}_s1`)).padStart(11, '0')}`,
    storeId: store.id,
    fulfillmentType: 'seller',
    sku: products[0].sku,
    productName: products[0].name,
    quantity: 1,
    amount: 39.99,
    currency: 'USD',
    status: pick(SELLER_ORDER_STATUSES.slice(0, 2), store.id, 10),
    orderedAt: buildTimeToday(10, 30),
    shipDeadline: `${todayKey()} 23:59:00`,
  })

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

export function syncTodayWalmartOrders(stores, options = {}) {
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
    message: options.refresh ? '已刷新 Walmart 今日订单' : undefined,
    data: {
      orders: state.items,
      syncedAt: state.syncedAt,
    },
  }
}

export function fetchCachedWalmartOrders(stores) {
  const state = ensureOrdersForStores(stores)
  return {
    success: true,
    data: {
      orders: state.items,
      syncedAt: state.syncedAt,
    },
  }
}

export function loadCachedWalmartOrders(stores) {
  return fetchCachedWalmartOrders(stores)
}
