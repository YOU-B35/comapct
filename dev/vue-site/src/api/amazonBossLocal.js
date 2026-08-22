import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { loadScoped, resolveTenantId, saveScoped } from '@/utils/tenantStorage'
import { TOP_PRODUCTS_SEED, OUTBOUND_ORDERS_SEED } from '@/constants/amazonBoss'

const STORAGE_KEY = 'crosshub_amazon_boss'

const EMPTY = { date: '', syncedAt: '', products: [], outboundOrders: [] }

function nowText() {
  return nowUtc8String()
}

function todayKey() {
  return nowUtc8DateString()
}

function loadAll(tenantId = resolveTenantId()) {
  return loadScoped(tenantId, STORAGE_KEY, EMPTY) || { ...EMPTY }
}

function saveAll(state, tenantId = resolveTenantId()) {
  saveScoped(tenantId, STORAGE_KEY, state)
}

function mergeSeeds(existing, seeds, boundIds) {
  const byId = Object.fromEntries(existing.map((item) => [item.id, item]))
  const merged = seeds.filter((s) => boundIds.has(s.storeId)).map((s) => byId[s.id] || { ...s })
  const seedIds = new Set(seeds.map((s) => s.id))
  const custom = existing.filter((item) => !seedIds.has(item.id) && boundIds.has(item.storeId))
  return [...merged, ...custom]
}

function normalizeOutboundDates(orders) {
  const date = todayKey()
  return orders.map((order) => ({
    ...order,
    orderedAt: order.orderedAt?.replace(/^\d{4}-\d{2}-\d{2}/, date) || order.orderedAt,
    shipDeadline: order.shipDeadline
      ? order.shipDeadline.replace(/^\d{4}-\d{2}-\d{2}/, date)
      : null,
  }))
}

export function ensureAmazonBossData(stores = []) {
  const boundIds = new Set(stores.map((s) => s.id))
  const state = loadAll()
  const date = todayKey()

  let products = state.date === date ? [...state.products] : []
  if (state.date !== date) {
    products = TOP_PRODUCTS_SEED.filter((p) => boundIds.has(p.storeId))
  }

  products = mergeSeeds(products, TOP_PRODUCTS_SEED, boundIds)
  products = products.filter((p) => boundIds.has(p.storeId))

  let outboundOrders = state.date === date ? [...state.outboundOrders] : []
  if (state.date !== date) {
    outboundOrders = normalizeOutboundDates(
      OUTBOUND_ORDERS_SEED.filter((o) => boundIds.has(o.storeId)),
    )
  }

  outboundOrders = mergeSeeds(outboundOrders, normalizeOutboundDates(OUTBOUND_ORDERS_SEED), boundIds)
  outboundOrders = outboundOrders.filter((o) => boundIds.has(o.storeId))

  const next = {
    date,
    syncedAt: state.syncedAt || nowText(),
    products,
    outboundOrders,
  }
  saveAll(next)
  return next
}

export function fetchAmazonBossData(stores = []) {
  const state = ensureAmazonBossData(stores)
  return {
    success: true,
    data: {
      products: state.products,
      outboundOrders: state.outboundOrders,
      syncedAt: state.syncedAt,
    },
  }
}

export async function syncAmazonBossData(stores = [], options = {}) {
  const state = ensureAmazonBossData(stores)
  if (options.refresh) {
    state.syncedAt = nowText()
    saveAll(state)
  }
  return {
    success: true,
    message: options.refresh ? '已刷新产品与销售数据' : undefined,
    data: {
      products: state.products,
      outboundOrders: state.outboundOrders,
      syncedAt: state.syncedAt,
    },
  }
}

export function markOutboundShipped(id, payload = {}) {
  const state = loadAll()
  const index = state.outboundOrders.findIndex((o) => o.id === id)
  if (index === -1) throw new Error('订单不存在')

  state.outboundOrders[index] = {
    ...state.outboundOrders[index],
    status: 'shipped',
    trackingNo: payload.trackingNo || state.outboundOrders[index].trackingNo || '',
    shippedAt: nowText(),
  }
  saveAll(state)
  return { success: true, data: state.outboundOrders[index] }
}
