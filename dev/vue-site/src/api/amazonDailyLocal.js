import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { loadScoped, resolveTenantId, saveScoped } from '@/utils/tenantStorage'
import {
  ACCOUNT_METRICS_SEED,
  BUYER_MESSAGES_SEED,
  CASES_SEED,
  COUPONS_SEED,
  REVIEWS_SEED,
  SELLER_NEWS_SEED,
  SHIPMENTS_SEED,
} from '@/constants/amazonDaily'

const STORAGE_KEY = 'crosshub_amazon_daily'

const EMPTY = {
  buyerMessages: [],
  accountMetrics: [],
  reviews: [],
  coupons: [],
  sellerNews: [],
  shipments: [],
  cases: [],
  syncedAt: '',
}

function loadAll(tenantId = resolveTenantId()) {
  const data = loadScoped(tenantId, STORAGE_KEY, null)
  return data ? { ...EMPTY, ...data } : { ...EMPTY }
}

function saveAll(data, tenantId = resolveTenantId()) {
  saveScoped(tenantId, STORAGE_KEY, data)
}

function nowText() {
  return nowUtc8String()
}

function mergeSeeds(existing, seeds, boundIds, idKey = 'id') {
  const byId = Object.fromEntries(existing.map((item) => [item[idKey], item]))
  const seedIds = new Set(seeds.map((item) => item[idKey]))
  for (const seed of seeds) {
    if (!boundIds.has(seed.storeId)) continue
    if (!byId[seed[idKey]]) byId[seed[idKey]] = { ...seed }
  }
  const custom = existing.filter((item) => !seedIds.has(item[idKey]) && boundIds.has(item.storeId))
  const merged = seeds.filter((s) => boundIds.has(s.storeId)).map((s) => byId[s[idKey]] || { ...s })
  return [...merged, ...custom]
}

function filterByStores(items, boundIds) {
  return (items || []).filter((item) => boundIds.has(item.storeId))
}

/** 为已绑定店铺注入 / 补齐一日运营 Demo 数据 */
export function ensureAmazonDailyData(stores = []) {
  const boundIds = new Set(stores.map((s) => s.id))
  const current = loadAll()

  const data = {
    buyerMessages: mergeSeeds(current.buyerMessages, BUYER_MESSAGES_SEED, boundIds),
    accountMetrics: mergeSeeds(current.accountMetrics, ACCOUNT_METRICS_SEED, boundIds),
    reviews: mergeSeeds(current.reviews, REVIEWS_SEED, boundIds),
    coupons: mergeSeeds(current.coupons, COUPONS_SEED, boundIds),
    sellerNews: mergeSeeds(current.sellerNews, SELLER_NEWS_SEED, boundIds),
    shipments: mergeSeeds(current.shipments, SHIPMENTS_SEED, boundIds),
    cases: mergeSeeds(current.cases, CASES_SEED, boundIds),
    syncedAt: current.syncedAt || nowText(),
  }

  saveAll(data)
  return data
}

function sliceForStores(data, stores) {
  const boundIds = new Set(stores.map((s) => s.id))
  return {
    buyerMessages: filterByStores(data.buyerMessages, boundIds),
    accountMetrics: filterByStores(data.accountMetrics, boundIds),
    reviews: filterByStores(data.reviews, boundIds),
    coupons: filterByStores(data.coupons, boundIds),
    sellerNews: filterByStores(data.sellerNews, boundIds),
    shipments: filterByStores(data.shipments, boundIds),
    cases: filterByStores(data.cases, boundIds),
    syncedAt: data.syncedAt,
  }
}

export function fetchAmazonDailyData(stores = []) {
  const data = ensureAmazonDailyData(stores)
  return { success: true, data: sliceForStores(data, stores) }
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function syncAmazonDailyData(stores = [], { refresh = false } = {}) {
  await delay(refresh ? 700 : 200)
  const data = ensureAmazonDailyData(stores)
  const syncedAt = nowText()
  const next = { ...data, syncedAt }
  saveAll(next)
  return {
    success: true,
    message: refresh ? '已刷新今日运营数据' : '已同步今日运营数据',
    data: { ...sliceForStores(next, stores), syncedAt },
  }
}

export function markBuyerMessageReplied(id, { templateId, note = '' } = {}) {
  const data = loadAll()
  const index = data.buyerMessages.findIndex((m) => m.id === id)
  if (index === -1) throw new Error('消息不存在')
  data.buyerMessages[index] = {
    ...data.buyerMessages[index],
    status: 'replied',
    repliedAt: nowText(),
    templateUsed: templateId || null,
    replyNote: note,
  }
  saveAll(data)
  return { success: true, data: data.buyerMessages[index] }
}

export function markReviewHandled(id, { note = '' } = {}) {
  const data = loadAll()
  const index = data.reviews.findIndex((r) => r.id === id)
  if (index === -1) throw new Error('评价不存在')
  data.reviews[index] = {
    ...data.reviews[index],
    status: 'handled',
    handledAt: nowText(),
    handleNote: note,
  }
  saveAll(data)
  return { success: true, data: data.reviews[index] }
}

export function markCaseRead(id) {
  const data = loadAll()
  const index = data.cases.findIndex((c) => c.id === id)
  if (index === -1) throw new Error('Case 不存在')
  data.cases[index] = {
    ...data.cases[index],
    read: true,
    hasNewReply: false,
  }
  saveAll(data)
  return { success: true, data: data.cases[index] }
}

/** @deprecated 兼容旧引用，转调 ensureAmazonDailyData */
export function ensureAmazonDemoData(stores) {
  return ensureAmazonDailyData(stores)
}
