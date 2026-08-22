import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { loadScoped, resolveTenantId, saveScoped } from '@/utils/tenantStorage'
import {
  ALIEXPRESS_OPERATOR,
  ALIEXPRESS_VIOLATIONS_SEED,
  VIOLATION_TYPES,
} from '@/constants/aliexpressDemo'

const STORAGE_KEY = 'crosshub_aliexpress_violations'

const EMPTY = { syncedAt: '', items: [] }

function loadAll(tenantId = resolveTenantId()) {
  return loadScoped(tenantId, STORAGE_KEY, EMPTY) || { ...EMPTY }
}

function saveAll(state, tenantId = resolveTenantId()) {
  saveScoped(tenantId, STORAGE_KEY, state)
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

function varyFine(base, storeId, index) {
  const hash = hashStoreId(`${storeId}_fine_${index}`)
  const ratio = 1 + ((hash % 100) / 100 - 0.5) * 0.2
  return Number((base * ratio).toFixed(2))
}

function buildTimeToday(hour, minute) {
  const date = nowUtc8DateString()
  return `${date} ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00`
}

function randomOrderNo(storeId, index) {
  const base = hashStoreId(`${storeId}_vio_${index}`)
  return `3300${String(base).padStart(10, '0').slice(0, 10)}`
}

function normalizeViolation(item) {
  return {
    appealResult: null,
    appealResultAt: null,
    ...item,
    appealResult:
      item.appealStatus === 'appealed' ? item.appealResult || null : null,
  }
}

function generateViolationsForStore(store) {
  const count = 2 + (hashStoreId(store.id) % 2)
  const items = []

  for (let i = 0; i < count; i += 1) {
    const type = pick(VIOLATION_TYPES, store.id, i)
    items.push({
      id: `vio_${store.id}_${i + 1}`,
      storeId: store.id,
      typeCode: type.code,
      typeLabel: type.label,
      orderNo: randomOrderNo(store.id, i),
      description: `${type.label}违规记录，系统自动抓取`,
      fineAmount: varyFine(type.defaultFine, store.id, i),
      currency: 'USD',
      violatedAt: buildTimeToday(8 + i * 3, 15 + i * 10),
      appealStatus: null,
      appealResult: null,
      confirmed: false,
      appealNote: '',
      confirmedAt: null,
      confirmedBy: null,
      appealResultAt: null,
    })
  }

  return items
}

function mergeSeedViolations(existingItems, boundIds) {
  const byId = Object.fromEntries(existingItems.map((item) => [item.id, item]))
  const seedIds = new Set(ALIEXPRESS_VIOLATIONS_SEED.map((item) => item.id))

  for (const seed of ALIEXPRESS_VIOLATIONS_SEED) {
    if (!boundIds.has(seed.storeId)) continue
    if (!byId[seed.id]) {
      byId[seed.id] = { ...seed }
    }
  }

  const custom = existingItems.filter((item) => !seedIds.has(item.id) && boundIds.has(item.storeId))
  const seeds = ALIEXPRESS_VIOLATIONS_SEED.filter((item) => boundIds.has(item.storeId)).map(
    (item) => byId[item.id] || { ...item },
  )

  return [...seeds, ...custom].map(normalizeViolation)
}

function ensureStoreViolations(stores, existingItems) {
  const boundIds = new Set(stores.map((store) => store.id))
  let items = mergeSeedViolations(existingItems, boundIds)
  items = items.filter((item) => boundIds.has(item.storeId))

  const seededStoreIds = new Set(ALIEXPRESS_VIOLATIONS_SEED.map((item) => item.storeId))
  for (const store of stores) {
    if (seededStoreIds.has(store.id)) continue
    const hasItems = items.some((item) => item.storeId === store.id)
    if (!hasItems) {
      items.push(...generateViolationsForStore(store))
    }
  }

  return items
}

function syncAppealResultsFromPlatform(items) {
  const today = nowUtc8DateString()
  return items.map((item) => {
    if (item.appealStatus !== 'appealed' || item.appealResult !== 'pending') {
      return item
    }
    const hash = hashStoreId(`${item.id}_${today}`)
    if (hash % 4 === 0) {
      return { ...item, appealResult: 'success', appealResultAt: nowText() }
    }
    if (hash % 7 === 0) {
      return { ...item, appealResult: 'failed', appealResultAt: nowText() }
    }
    return item
  })
}

function delay(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

/** 爬取 / 同步违规信息（Demo 模拟） */
export async function syncAliExpressViolations(stores = [], { refresh = false } = {}) {
  await delay(refresh ? 800 : 300)

  const current = loadAll()
  let items = ensureStoreViolations(stores, current.items)

  if (refresh) {
    const boundIds = new Set(stores.map((store) => store.id))
    items = syncAppealResultsFromPlatform(items)
    const newViolation = normalizeViolation({
      id: `vio_new_${Date.now()}`,
      storeId: stores[0]?.id,
      typeCode: 'pickup_timeout',
      typeLabel: '揽收超时',
      orderNo: randomOrderNo(stores[0]?.id || 'store', 99),
      description: '最新爬取：揽收超时违规，待运营确认申诉状态',
      fineAmount: 15,
      currency: 'USD',
      violatedAt: nowText(),
      appealStatus: null,
      appealResult: null,
      confirmed: false,
      appealNote: '',
      confirmedAt: null,
      confirmedBy: null,
      appealResultAt: null,
    })
    if (newViolation.storeId && boundIds.has(newViolation.storeId)) {
      items = [newViolation, ...items]
    }
  }

  const syncedAt = nowText()
  saveAll({ syncedAt, items })

  return {
    success: true,
    message: refresh ? '已刷新违规信息' : '已同步违规信息',
    data: { violations: items, syncedAt },
  }
}

export function fetchAliExpressViolations(stores = []) {
  const current = loadAll()
  const boundIds = new Set(stores.map((store) => store.id))
  const items = ensureStoreViolations(stores, current.items).filter((item) =>
    boundIds.has(item.storeId),
  )

  if (items.length !== current.items.length) {
    saveAll({ syncedAt: current.syncedAt || nowText(), items })
  }

  return {
    success: true,
    data: {
      violations: items,
      syncedAt: current.syncedAt || '',
    },
  }
}

export function confirmViolationAppeal(id, payload) {
  const current = loadAll()
  const index = current.items.findIndex((item) => item.id === id)
  if (index === -1) {
    throw new Error('违规记录不存在')
  }

  const { appealStatus, appealNote, appealResult } = payload
  if (!appealStatus) {
    throw new Error('请选择是否已申诉')
  }

  const nextAppealResult =
    appealStatus === 'appealed' ? appealResult || 'pending' : null

  current.items[index] = {
    ...current.items[index],
    appealStatus,
    appealResult: nextAppealResult,
    appealNote: String(appealNote || '').trim(),
    confirmed: true,
    confirmedAt: nowText(),
    confirmedBy: ALIEXPRESS_OPERATOR.name,
    appealResultAt: nextAppealResult ? nowText() : null,
  }

  saveAll(current)
  return { success: true, data: { ...current.items[index] } }
}

export function updateViolationAppealDraft(id, payload) {
  const current = loadAll()
  const index = current.items.findIndex((item) => item.id === id)
  if (index === -1) {
    throw new Error('违规记录不存在')
  }

  current.items[index] = {
    ...current.items[index],
    appealStatus: payload.appealStatus ?? current.items[index].appealStatus,
    appealNote: payload.appealNote ?? current.items[index].appealNote,
  }

  saveAll(current)
  return { success: true, data: { ...current.items[index] } }
}
