import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { loadScoped, resolveTenantId, saveScoped } from '@/utils/tenantStorage'
import {
  ALIEXPRESS_ORDER_COUNTRIES,
  ALIEXPRESS_ORDERS_SEED,
  ALIEXPRESS_WAREHOUSES,
  JIT_ORDER_STATUSES,
  WAREHOUSE_ORDER_STATUSES,
} from '@/constants/aliexpressDemo'

const ORDERS_STORAGE_KEY = 'crosshub_aliexpress_orders'

function todayKey() {
  return nowUtc8DateString()
}

function nowText() {
  return nowUtc8String()
}

const EMPTY_ORDERS = { date: '', syncedAt: '', items: [] }

function loadOrdersState(tenantId = resolveTenantId()) {
  return loadScoped(tenantId, ORDERS_STORAGE_KEY, EMPTY_ORDERS) || { ...EMPTY_ORDERS }
}

function saveOrdersState(state, tenantId = resolveTenantId()) {
  saveScoped(tenantId, ORDERS_STORAGE_KEY, state)
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

function randomOrderNo(storeId, index, prefix) {
  const base = hashStoreId(`${storeId}_${index}_${todayKey()}`)
  return `${prefix}${String(base).padStart(13, '0').slice(0, 13)}`
}

function buildTimeToday(hour, minute) {
  const date = todayKey()
  return `${date} ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00`
}

function buildShipDeadline(hour) {
  const date = todayKey()
  return `${date} ${String(hour).padStart(2, '0')}:00:00`
}

function generateOrdersForStore(store, products) {
  const storeProducts = products.filter((item) => item.storeId === store.id)
  if (!storeProducts.length) return []

  const orders = []
  const jitCount = 2 + (hashStoreId(store.id) % 2)
  const warehouseCount = 1 + (hashStoreId(`${store.id}_wh`) % 2)

  for (let i = 0; i < jitCount; i += 1) {
    const product = storeProducts[i % storeProducts.length]
    const hour = 7 + i * 2
    const quantity = 1 + (hashStoreId(`${store.id}_q${i}`) % 3)
    orders.push({
      id: `ae_order_jit_${store.id}_${i + 1}`,
      orderNo: randomOrderNo(store.id, i, '3300'),
      storeId: store.id,
      fulfillmentType: 'jit',
      sku: product.sku,
      productName: product.name,
      quantity,
      amount: Number((product.sellingPrice * quantity).toFixed(2)),
      currency: 'USD',
      country: pick(ALIEXPRESS_ORDER_COUNTRIES, store.id, i),
      status: pick(JIT_ORDER_STATUSES.slice(0, 3), store.id, i + 10),
      orderedAt: buildTimeToday(hour, 10 + i * 8),
      shipDeadline: buildShipDeadline(16 + i),
      warehouseName: null,
    })
  }

  for (let i = 0; i < warehouseCount; i += 1) {
    const product = storeProducts[(i + 1) % storeProducts.length]
    const hour = 5 + i * 3
    orders.push({
      id: `ae_order_wh_${store.id}_${i + 1}`,
      orderNo: randomOrderNo(store.id, i + 20, '3309'),
      storeId: store.id,
      fulfillmentType: 'warehouse',
      sku: product.sku,
      productName: product.name,
      quantity: 1,
      amount: product.sellingPrice,
      currency: 'USD',
      country: pick(ALIEXPRESS_ORDER_COUNTRIES, store.id, i + 30),
      status: pick(WAREHOUSE_ORDER_STATUSES, store.id, i + 40),
      orderedAt: buildTimeToday(hour, 20 + i * 5),
      shipDeadline: null,
      warehouseName: pick(ALIEXPRESS_WAREHOUSES, store.id, i + 50),
    })
  }

  return orders
}

function normalizeSeedOrders() {
  const date = todayKey()
  return ALIEXPRESS_ORDERS_SEED.map((order) => ({
    ...order,
    orderedAt: order.orderedAt.replace(/^\d{4}-\d{2}-\d{2}/, date),
    shipDeadline: order.shipDeadline
      ? order.shipDeadline.replace(/^\d{4}-\d{2}-\d{2}/, date)
      : null,
  }))
}

function buildTodayOrders(stores, products) {
  const boundIds = new Set(stores.map((store) => store.id))
  const seedOrders = normalizeSeedOrders().filter((order) => boundIds.has(order.storeId))
  const seededStoreIds = new Set(seedOrders.map((order) => order.storeId))

  const generated = stores
    .filter((store) => !seededStoreIds.has(store.id))
    .flatMap((store) => generateOrdersForStore(store, products))

  return [...seedOrders, ...generated]
}

function delay(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

/** 同步当日 JIT / 仓发订单（Demo 模拟实时抓取） */
export async function syncTodayAliExpressOrders(stores = [], products = [], { refresh = false } = {}) {
  await delay(refresh ? 900 : 300)

  const today = todayKey()
  const current = loadOrdersState()
  const boundIds = new Set(stores.map((store) => store.id))

  let items = current.items.filter((order) => boundIds.has(order.storeId))

  if (current.date !== today || refresh || !items.length) {
    items = buildTodayOrders(stores, products)
  } else if (refresh) {
    items = items.map((order, index) => ({
      ...order,
      orderedAt: buildTimeToday(6 + (index % 8), (index * 7) % 60),
      syncedAt: nowText(),
    }))
  }

  const syncedAt = nowText()
  items = items.map((order) => ({ ...order, syncedAt }))

  const state = { date: today, syncedAt, items }
  saveOrdersState(state)

  return {
    success: true,
    message: refresh ? '已刷新当日实时订单' : '已抓取当日订单',
    data: {
      orders: items,
      syncedAt,
      date: today,
    },
  }
}

export function fetchCachedAliExpressOrders(stores = []) {
  const current = loadOrdersState()
  const boundIds = new Set(stores.map((store) => store.id))
  const today = todayKey()

  return {
    success: true,
    data: {
      orders: current.date === today ? current.items.filter((order) => boundIds.has(order.storeId)) : [],
      syncedAt: current.syncedAt || '',
      date: current.date || today,
    },
  }
}
