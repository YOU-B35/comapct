import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import {
  ORDER_STATUS_MAP,
  SOURCE_TYPE_OPTIONS,
  WAREHOUSE_ORDERS_SEED,
  WAREHOUSE_ORDER_STORAGE_KEY,
} from '@/constants/warehouseOrders'
import { MARKETPLACE_PLATFORM_OPTIONS, DTC_PLATFORM_OPTIONS } from '@/constants/platforms'
import { PLATFORM_ORDER_LABELS } from '@/constants/platformShipRequests'
import { normalizeUploadedFiles } from '@/utils/warehouseOrders'
import { findLocalWarehouseSite } from '@/api/warehouseSitesLocal'
import { syncPlatformOrderFromWarehouseOrder } from '@/api/platformOrderWarehouseSync'
import { loadScoped, resolveTenantId, saveScoped, isDemoTemplateEnabled } from '@/utils/tenantStorage'

const SEED_FLAG_KEY = 'crosshub_warehouse_orders_seeded'

const PLATFORM_LABELS = {
  ...Object.fromEntries(
    [...MARKETPLACE_PLATFORM_OPTIONS, ...DTC_PLATFORM_OPTIONS].map((item) => [item.value, item.label]),
  ),
  ...PLATFORM_ORDER_LABELS,
}

function nowText() {
  return nowUtc8String()
}

function persistLinkedPlatformOrder(order) {
  if (order?.fromPlatformOrder) {
    syncPlatformOrderFromWarehouseOrder(order)
  }
  return order
}

function loadAll(tenantId = resolveTenantId()) {
  return loadScoped(tenantId, WAREHOUSE_ORDER_STORAGE_KEY, []) || []
}

function saveAll(items, tenantId = resolveTenantId()) {
  saveScoped(tenantId, WAREHOUSE_ORDER_STORAGE_KEY, items)
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('crosshub-warehouse-orders-changed'))
  }
}

function ensureSeed(tenantId = resolveTenantId()) {
  if (!isDemoTemplateEnabled(tenantId)) return
  if (loadScoped(tenantId, SEED_FLAG_KEY)) {
    patchSeedWarehouses(tenantId)
    return
  }
  const existing = loadAll(tenantId)
  const ids = new Set(existing.map((item) => item.id))
  const merged = [...existing, ...WAREHOUSE_ORDERS_SEED.filter((item) => !ids.has(item.id))]
  saveAll(merged, tenantId)
  saveScoped(tenantId, SEED_FLAG_KEY, '1')
}

function patchSeedWarehouses(tenantId = resolveTenantId()) {
  const seedById = Object.fromEntries(WAREHOUSE_ORDERS_SEED.map((item) => [item.id, item]))
  const items = loadAll(tenantId)
  let changed = false
  const next = items.map((item) => {
    const seed = seedById[item.id]
    if (!seed || item.warehouseId) return item
    changed = true
    return { ...item, warehouseId: seed.warehouseId, warehouseName: seed.warehouseName }
  })
  if (changed) saveAll(next, tenantId)
}

function nextOrderNo() {
  const date = nowUtc8DateString().replace(/-/g, '')
  const count = loadAll().filter((item) => String(item.orderNo || '').includes(date)).length + 1
  return `WH${date}${String(count).padStart(3, '0')}`
}

function buildSourceLabel(payload) {
  if (payload.sourceType === 'b2b') {
    const name = (payload.b2bCustomerName || '').trim()
    return name ? `B 端 · ${name}` : 'B 端客户货'
  }
  const platform = PLATFORM_LABELS[payload.sourcePlatform] || payload.sourcePlatform || '电商平台'
  const store = (payload.sourceStoreName || '').trim()
  return store ? `${platform} · ${store}` : platform
}

export function fetchLocalWarehouseOrders(filters = {}) {
  ensureSeed()
  let items = loadAll()

  if (filters.submittedById) {
    items = items.filter((item) => item.submittedById === filters.submittedById)
  }
  if (filters.status) {
    items = items.filter((item) => item.status === filters.status)
  }
  if (filters.sourceType) {
    items = items.filter((item) => item.sourceType === filters.sourceType)
  }
  if (filters.pendingReviewOnly) {
    items = items.filter((item) => item.status === 'pending_review')
  }
  if (filters.warehouseIds?.length) {
    const allowed = new Set(filters.warehouseIds)
    items = items.filter((item) => allowed.has(item.warehouseId))
  } else if (Array.isArray(filters.warehouseIds) && filters.warehouseIds.length === 0) {
    items = []
  }

  return items.sort((a, b) => String(b.submittedAt).localeCompare(String(a.submittedAt)))
}

export function fetchLocalWarehouseOrderById(id) {
  ensureSeed()
  return loadAll().find((item) => item.id === id) || null
}

/** 运营/管理员催促发货 → 追加至出库单 */
export function appendLocalWarehouseShipUrge(warehouseOrderId, { remark, submitter }) {
  ensureSeed()
  const items = loadAll()
  const index = items.findIndex((item) => item.id === warehouseOrderId)
  if (index === -1) throw new Error('出库单不存在')

  const order = items[index]
  if (order.status === 'shipped' || order.status === 'cancelled') {
    throw new Error('出库单已完成或已取消，无法催促')
  }

  const urges = [...(order.shipUrges || [])]
  urges.unshift({
    id: `urge_${Date.now()}`,
    type: 'urge',
    remark: (remark || '').trim(),
    by: submitter.id,
    byName: submitter.name,
    at: nowText(),
  })

  items[index] = {
    ...order,
    shipUrges: urges,
    shipRequestType: 'urge',
    lastUrgedAt: nowText(),
    updatedAt: nowText(),
    remark: [order.remark, `[催促 ${nowText()}] ${submitter.name}：${(remark || '').trim()}`]
      .filter(Boolean)
      .join('\n'),
  }
  saveAll(items)
  return items[index]
}

export function createLocalWarehouseOrder(payload, submitter) {
  ensureSeed()
  const items = loadAll()

  if (!payload.items?.length) {
    throw new Error('请至少添加一条货品明细')
  }
  if (payload.items.some((row) => !row.productName?.trim() || !row.quantity || row.quantity <= 0)) {
    throw new Error('请完善货品名称与数量')
  }
  if (payload.sourceType === 'b2b' && !payload.b2bCustomerName?.trim()) {
    throw new Error('请填写 B 端客户名称')
  }
  if (payload.sourceType === 'marketplace' && !payload.sourcePlatform) {
    throw new Error('请选择电商平台')
  }
  if (!payload.warehouseId) {
    throw new Error('请选择出库仓库')
  }
  const site = findLocalWarehouseSite(payload.warehouseId)
  if (!site || site.status === false) {
    throw new Error('目标仓库不存在或已停用')
  }

  const row = {
    id: `wh_ord_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    orderNo: nextOrderNo(),
    status: 'pending_review',
    warehouseId: site.id,
    warehouseName: site.name,
    items: payload.items.map((item, index) => ({
      id: item.id || `li_${Date.now()}_${index}`,
      productName: item.productName.trim(),
      sku: (item.sku || '').trim(),
      quantity: Number(item.quantity),
      unit: item.unit || '件',
    })),
    remark: (payload.remark || '').trim(),
    sourceType: payload.sourceType || 'marketplace',
    sourcePlatform: payload.sourcePlatform || '',
    sourceStoreName: (payload.sourceStoreName || '').trim(),
    sourceLabel: buildSourceLabel(payload),
    b2bCustomerName: (payload.b2bCustomerName || '').trim(),
    attachments: normalizeUploadedFiles(payload.attachments, 'att'),
    cartonMarks: normalizeUploadedFiles(payload.cartonMarks, 'cm'),
    labels: normalizeUploadedFiles(payload.labels, 'lb'),
    submittedByRole: submitter.role,
    submittedById: submitter.id,
    submittedByName: submitter.name,
    submittedAt: nowText(),
    platformOrderId: payload.platformOrderId || '',
    platformOrderNo: payload.platformOrderNo || '',
    platformStoreId: payload.platformStoreId || '',
    shipRequestType: payload.shipRequestType || '',
    shipUrges: [],
    fromPlatformOrder: Boolean(payload.fromPlatformOrder),
    warehouseReview: null,
    updatedAt: nowText(),
  }

  items.unshift(row)
  saveAll(items)
  return row
}

export function submitLocalWarehouseReview(orderId, reviewPayload, reviewer) {
  ensureSeed()
  const items = loadAll()
  const index = items.findIndex((item) => item.id === orderId)
  if (index === -1) throw new Error('订单不存在')

  const order = items[index]
  if (order.status === 'cancelled' || order.status === 'shipped') {
    throw new Error('当前订单状态不可审批')
  }

  const canShip = Boolean(reviewPayload.canShip)
  const review = {
    canShip,
    estimatedShipAt: (reviewPayload.estimatedShipAt || '').trim(),
    missingMaterials: (reviewPayload.missingMaterials || '').trim(),
    packagingNotes: (reviewPayload.packagingNotes || '').trim(),
    extraOrderNotes: (reviewPayload.extraOrderNotes || '').trim(),
    reviewRemark: (reviewPayload.reviewRemark || '').trim(),
    reviewedById: reviewer.id,
    reviewedByName: reviewer.name,
    reviewedAt: nowText(),
  }

  items[index] = {
    ...order,
    status: canShip ? 'pending_shipment' : 'blocked',
    warehouseReview: review,
    updatedAt: nowText(),
  }
  saveAll(items)
  return persistLinkedPlatformOrder(items[index])
}

export function updateLocalWarehouseOrderStatus(orderId, status) {
  ensureSeed()
  if (!ORDER_STATUS_MAP[status]) throw new Error('无效状态')
  const items = loadAll()
  const index = items.findIndex((item) => item.id === orderId)
  if (index === -1) throw new Error('订单不存在')
  items[index] = { ...items[index], status, updatedAt: nowText() }
  saveAll(items)
  return persistLinkedPlatformOrder(items[index])
}

export function cancelLocalWarehouseOrder(orderId) {
  return updateLocalWarehouseOrderStatus(orderId, 'cancelled')
}

export function deleteLocalWarehouseOrder(orderId) {
  ensureSeed()
  const items = loadAll()
  const index = items.findIndex((item) => item.id === orderId)
  if (index === -1) throw new Error('订单不存在')
  items.splice(index, 1)
  saveAll(items)
  return { deleted: true, id: orderId }
}

export function markLocalWarehouseOrderShipped(orderId) {
  const order = fetchLocalWarehouseOrderById(orderId)
  if (!order) throw new Error('订单不存在')
  if (order.status !== 'pending_shipment') {
    throw new Error('仅待发货订单可标记为已发货')
  }
  return updateLocalWarehouseOrderStatus(orderId, 'shipped')
}

/** 暂不可发 → 补货完成后确认可发，进入待发货 */
export function releaseLocalBlockedWarehouseOrder(orderId, releasePayload, reviewer) {
  ensureSeed()
  const items = loadAll()
  const index = items.findIndex((item) => item.id === orderId)
  if (index === -1) throw new Error('订单不存在')

  const order = items[index]
  if (order.status !== 'blocked') {
    throw new Error('仅暂不可发订单可确认可发')
  }

  const review = order.warehouseReview || {}
  items[index] = {
    ...order,
    status: 'pending_shipment',
    warehouseReview: {
      ...review,
      canShip: true,
      estimatedShipAt: (releasePayload.estimatedShipAt || '').trim(),
      releaseRemark: (releasePayload.releaseRemark || '').trim(),
      releasedById: reviewer.id,
      releasedByName: reviewer.name,
      releasedAt: nowText(),
    },
    updatedAt: nowText(),
  }
  saveAll(items)
  return persistLinkedPlatformOrder(items[index])
}

export function warehouseOrderStats(orders = []) {
  return {
    total: orders.length,
    pendingReview: orders.filter((item) => item.status === 'pending_review').length,
    pendingShipment: orders.filter((item) => item.status === 'pending_shipment').length,
    blocked: orders.filter((item) => item.status === 'blocked').length,
    shipped: orders.filter((item) => item.status === 'shipped').length,
  }
}

export { SOURCE_TYPE_OPTIONS }
