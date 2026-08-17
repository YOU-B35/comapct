import { PURCHASE_ORDER_STATUSES, SUPPLIER_ALERT_TYPES } from '@/constants/alibaba1688'
import { formatMoney } from '@/utils/format'

export function enrichPurchaseOrder(order) {
  const meta = PURCHASE_ORDER_STATUSES[order.status] || PURCHASE_ORDER_STATUSES.pending_payment
  return {
    ...order,
    statusLabel: meta.label,
    statusType: meta.type,
    amountText: formatMoney(order.amount || 0),
    isPending: order.status !== 'completed',
    isActionNeeded: ['pending_payment', 'pending_shipment'].includes(order.status),
    isDelayed: Boolean(order.isDelayed),
    isStockout: Boolean(order.isStockout),
    expectedArrivalAt: order.expectedArrivalAt || order.expected_arrival_at || '',
  }
}

export function enrichSupplierAlert(alert) {
  const meta = SUPPLIER_ALERT_TYPES[alert.type] || { label: alert.type, type: 'info' }
  const resolved = alert.resolved === true || alert.isOpen === false
  const severity = alert.severity || alert.level || 'medium'
  const detail = alert.detail || alert.message || ''
  return {
    ...alert,
    typeLabel: meta.label,
    typeTag: meta.type,
    severity,
    detail,
    isOpen: alert.isOpen === true || (!resolved && alert.resolved !== true),
  }
}

export function summarize1688PurchaseOrders(orders = []) {
  const enriched = orders.map(enrichPurchaseOrder)
  const totalAmount = enriched.reduce((sum, o) => sum + (o.amount || 0), 0)
  const pendingPayment = enriched.filter((o) => o.status === 'pending_payment')
  const pendingShipment = enriched.filter((o) => o.status === 'pending_shipment')
  const pendingReceive = enriched.filter((o) => o.status === 'pending_receive')
  const pending = enriched.filter((o) => o.isActionNeeded).length

  return {
    total: enriched.length,
    totalAmount,
    totalAmountText: formatMoney(totalAmount),
    pendingPayment: pendingPayment.length,
    pendingShipment: pendingShipment.length,
    pendingReceive: pendingReceive.length,
    pending,
    orders: enriched,
  }
}

export function summarize1688SupplierAlerts(alerts = []) {
  const enriched = alerts.map(enrichSupplierAlert)
  const open = enriched.filter((a) => a.isOpen)
  const high = open.filter((a) => a.severity === 'high')

  return {
    total: enriched.length,
    open: open.length,
    high: high.length,
    alerts: enriched,
  }
}

export function summarize1688ByStore(orders, alerts, stores = []) {
  return (stores || []).map((store) => {
    const storeOrders = orders.filter((o) => o.storeId === store.id)
    const storeAlerts = alerts.filter((a) => a.storeId === store.id)
    return {
      store,
      orders: summarize1688PurchaseOrders(storeOrders),
      alerts: summarize1688SupplierAlerts(storeAlerts),
    }
  })
}
