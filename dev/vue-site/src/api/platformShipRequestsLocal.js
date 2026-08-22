import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { PLATFORM_ORDER_STORAGE_KEYS } from '@/constants/platformShipRequests'
import {
  appendLocalWarehouseShipUrge,
  createLocalWarehouseOrder,
  fetchLocalWarehouseOrderById,
} from './warehouseOrdersLocal'
import {
  buildWarehouseFeedbackPatch,
  find1688PlatformOrder,
  findDomesticPlatformOrder,
  update1688PlatformOrder,
  updateDomesticPlatformOrder,
} from './platformOrderWarehouseSync'
import {
  buildWarehousePayloadFrom1688Order,
  buildWarehousePayloadFromDomesticOrder,
} from '@/utils/platformShipToWarehouse'

function nowText() {
  return nowUtc8String()
}

function resolveSubmitter(auth) {
  if (auth.isBoss) {
    return {
      id: auth.backendLinked ? String(auth.backendUserId || 'boss_admin') : 'boss_admin',
      name: auth.displayName || '企业管理员',
      role: 'boss',
    }
  }
  return {
    id: auth.backendLinked ? String(auth.backendUserId || auth.employee.id) : auth.employee.id,
    name: auth.employee.name,
    role: 'employee',
  }
}

function updateDomesticOrder(platformKey, orderId, patch) {
  return updateDomesticPlatformOrder(platformKey, orderId, patch)
}

function update1688Order(orderId, patch) {
  return update1688PlatformOrder(orderId, patch)
}

function linkPlatformOrder(platformKey, order, warehouseOrder, type) {
  const patch = {
    warehouseOrderId: warehouseOrder.id,
    warehouseOrderNo: warehouseOrder.orderNo,
    warehouseId: warehouseOrder.warehouseId,
    warehouseName: warehouseOrder.warehouseName,
    warehouseStatus: warehouseOrder.status,
    shipRequestType: type,
    shipPushedAt: type === 'push' ? nowText() : order.shipPushedAt,
    shipUrgedAt: type === 'urge' ? nowText() : order.shipUrgedAt,
    shipUrgeCount: type === 'urge' ? (Number(order.shipUrgeCount) || 0) + 1 : Number(order.shipUrgeCount) || 0,
  }

  if (platformKey === '1688') {
    return update1688Order(order.id, patch)
  }
  return updateDomesticOrder(platformKey, order.id, patch)
}

export function pushPlatformOrderToWarehouse(auth, {
  platformKey,
  order,
  storeName,
  warehouseId,
  type = 'push',
  remark = '',
}) {
  if (!order?.id) throw new Error('订单无效')

  const submitter = resolveSubmitter(auth)

  if (type === 'urge') {
    if (!order.warehouseOrderId) throw new Error('请先推送发货至仓库')
    const warehouseOrder = appendLocalWarehouseShipUrge(order.warehouseOrderId, { remark, submitter })
    const updated = linkPlatformOrder(platformKey, order, warehouseOrder, 'urge')
    return { warehouseOrder, platformOrder: updated }
  }

  if (order.warehouseOrderId) {
    throw new Error('该订单已推送至仓库，请使用「催促发货」')
  }
  if (!warehouseId) throw new Error('请选择出库仓库')

  const payload = platformKey === '1688'
    ? buildWarehousePayloadFrom1688Order(order, storeName, { warehouseId, type, remark })
    : buildWarehousePayloadFromDomesticOrder(order, platformKey, storeName, { warehouseId, type, remark })

  const warehouseOrder = createLocalWarehouseOrder(payload, submitter)
  const platformOrder = linkPlatformOrder(platformKey, order, warehouseOrder, 'push')
  return { warehouseOrder, platformOrder }
}

export function enrichOrderWithWarehouseFeedback(order) {
  if (!order?.warehouseOrderId) return order

  const wh = fetchLocalWarehouseOrderById(order.warehouseOrderId)
  if (!wh) return order

  const patch = buildWarehouseFeedbackPatch(wh)
  return patch ? { ...order, ...patch } : order
}

export function enrichOrdersWithWarehouseFeedback(orders = []) {
  return orders.map((order) => enrichOrderWithWarehouseFeedback(order))
}

export function syncPlatformOrderWarehouseStatus(platformKey, orderId) {
  if (platformKey === '1688') {
    const order = find1688PlatformOrder(orderId)
    if (!order?.warehouseOrderId) return order
    const wh = fetchLocalWarehouseOrderById(order.warehouseOrderId)
    if (!wh) return order
    const patch = buildWarehouseFeedbackPatch(wh)
    return patch ? update1688PlatformOrder(orderId, patch) : order
  }

  const order = findDomesticPlatformOrder(platformKey, orderId)
  if (!order?.warehouseOrderId) return order
  const wh = fetchLocalWarehouseOrderById(order.warehouseOrderId)
  if (!wh) return order
  const patch = buildWarehouseFeedbackPatch(wh)
  return patch ? updateDomesticPlatformOrder(platformKey, orderId, patch) : order
}
