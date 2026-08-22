import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
﻿import { loadScoped, resolveTenantId, saveScoped } from '@/utils/tenantStorage'
import { DTC_ORDERS_SEED } from '@/constants/dtcOrders'

const STORAGE_KEY = 'crosshub_dtc_orders'

function todayKey() {
  return nowUtc8DateString()
}

function loadState() {
  const tenantId = resolveTenantId()
  return loadScoped(tenantId, STORAGE_KEY, { date: '', items: [] })
    || { date: '', items: [] }
}

function saveState(state) {
  saveScoped(resolveTenantId(), STORAGE_KEY, state)
}

function normalizeOrders(date) {
  return DTC_ORDERS_SEED.map((order) => ({
    ...order,
    orderedAt: order.orderedAt.replace(/^\d{4}-\d{2}-\d{2}/, date),
    shippedAt: order.shippedAt
      ? order.shippedAt.replace(/^\d{4}-\d{2}-\d{2}/, date)
      : null,
  }))
}

export function loadDtcTodayOrders(stores = []) {
  const today = todayKey()
  const boundIds = new Set(stores.map((store) => store.id))
  const current = loadState()

  let items =
    current.date === today
      ? current.items
      : normalizeOrders(today)

  items = items.filter((order) => boundIds.has(order.storeId))

  if (current.date !== today || items.length !== current.items.length) {
    saveState({ date: today, items: normalizeOrders(today).filter((o) => boundIds.has(o.storeId)) })
  }

  return items
}

export function ensureDtcOrdersDemo(stores = []) {
  loadDtcTodayOrders(stores)
}

