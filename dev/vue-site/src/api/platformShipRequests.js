import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { hasBackendSession } from './backendSession'
import { createBackendWarehouseOrderFromPlatform, fetchBackendWarehouseOrders } from './warehouseOrdersApi'
import { buildWarehouseFeedbackPatch } from './platformOrderWarehouseSync'
import {
  pushPlatformOrderToWarehouse as pushLocal,
  enrichOrdersWithWarehouseFeedback as enrichLocalOrders,
  enrichOrderWithWarehouseFeedback as enrichLocalOrder,
} from './platformShipRequestsLocal'

function platformOrderRef(platformKey, orderId) {
  return `${platformKey}:${orderId}`
}

async function findBackendWarehouseOrderByRef(ref) {
  const data = await fetchBackendWarehouseOrders()
  return (data?.orders || []).find((item) => item.sourceOrderRef === ref) || null
}

function patchOrderFromWarehouse(order, warehouseOrder) {
  const patch = buildWarehouseFeedbackPatch(warehouseOrder)
  return patch ? { ...order, ...patch } : order
}

/** 平台订单推送 / 催促发货至仓库 */
export async function pushPlatformOrderToWarehouse(auth, payload) {
  if (!hasBackendSession(auth)) {
    const result = pushLocal(auth, payload)
    return {
      success: true,
      message: payload.type === 'urge'
        ? `已催促 ${result.warehouseOrder.warehouseName} 发货`
        : `已推送至 ${result.warehouseOrder.warehouseName}，等待仓库审核`,
      data: result,
    }
  }

  const { platformKey, order, storeName, warehouseId, type = 'push', remark = '' } = payload
  if (!order?.id) throw new Error('订单无效')

  const sourceOrderRef = platformOrderRef(platformKey, order.id)

  if (type === 'urge') {
    const existing = await findBackendWarehouseOrderByRef(sourceOrderRef)
    if (!existing) throw new Error('请先推送发货至仓库')
    return {
      success: true,
      message: `已记录催促，仓库 ${existing.warehouseName || ''} 处理中`,
      data: {
        warehouseOrder: existing,
        platformOrder: patchOrderFromWarehouse(order, existing),
      },
    }
  }

  if (order.warehouseOrderId || order.sourceOrderRef) {
    throw new Error('该订单已推送至仓库，请使用「催促发货」')
  }
  if (!warehouseId) throw new Error('请选择出库仓库')

  const body = {
    warehouseId,
    sourceType: 'marketplace',
    sourcePlatform: platformKey,
    sourceStoreName: storeName,
    sourceOrderRef,
    fromPlatformOrder: true,
    remark: remark || `平台订单 ${order.orderNo || order.id} 推送发货`,
    items: [
      {
        productName: order.productName || order.title || '平台订单商品',
        sku: order.sku || '',
        quantity: Number(order.quantity) || 1,
        unit: '件',
      },
    ],
    attachments: [],
    cartonMarks: [],
    labels: [],
  }

  const warehouseOrder = await createBackendWarehouseOrderFromPlatform(body)
  const platformOrder = {
    ...order,
    warehouseOrderId: warehouseOrder.id,
    warehouseOrderNo: warehouseOrder.orderNo,
    warehouseId: warehouseOrder.warehouseId,
    warehouseName: warehouseOrder.warehouseName,
    warehouseStatus: warehouseOrder.status,
    sourceOrderRef,
    shipRequestType: 'push',
    shipPushedAt: nowUtc8String(),
  }

  return {
    success: true,
    message: `已推送至 ${warehouseOrder.warehouseName}，等待仓库审核`,
    data: { warehouseOrder, platformOrder },
  }
}

export async function enrichOrdersWithWarehouseFeedback(orders = [], auth = null) {
  if (!hasBackendSession(auth)) {
    return enrichLocalOrders(orders)
  }

  const data = await fetchBackendWarehouseOrders()
  const byRef = new Map(
    (data?.orders || [])
      .filter((item) => item.sourceOrderRef)
      .map((item) => [item.sourceOrderRef, item]),
  )

  return orders.map((order) => {
    const ref = order.sourceOrderRef || platformOrderRef(order.platformKey || '', order.id)
    const wh = order.warehouseOrderId
      ? (data?.orders || []).find((item) => item.id === order.warehouseOrderId)
      : byRef.get(ref)
    return wh ? patchOrderFromWarehouse(order, wh) : order
  })
}

export async function enrichOrderWithWarehouseFeedback(order, auth = null) {
  if (!hasBackendSession(auth)) {
    return enrichLocalOrder(order)
  }
  const rows = await enrichOrdersWithWarehouseFeedback([order], auth)
  return rows[0]
}
