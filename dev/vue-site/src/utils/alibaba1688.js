import { PURCHASE_ORDER_STATUSES, SUPPLIER_ALERT_TYPES } from '../constants/alibaba1688.js'
import { formatMoney } from './format.js'

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

export function parse1688Money(value) {
  if (value == null || value === '') return 0
  if (typeof value === 'number' && Number.isFinite(value)) return value
  const cleaned = String(value).replace(/[^\d.-]/g, '')
  const n = Number(cleaned)
  return Number.isFinite(n) ? n : 0
}

export function summarize1688ProductGmv(products = []) {
  const list = Array.isArray(products) ? products : []
  let totalGmv = 0
  let soldCount = 0
  for (const p of list) {
    const gmv = parse1688Money(p?.gmv1d ?? p?.gmv_1d)
    totalGmv += gmv
    if (gmv > 0) soldCount += 1
  }
  return {
    totalGmv,
    totalGmvText: formatMoney(totalGmv),
    productCount: list.length,
    soldCount,
    products: list,
  }
}

export function filterItemsByStoreIds(items, storeIds) {
  const list = items || []
  const set = new Set(storeIds || [])
  const matched = list.filter((item) => set.has(item.storeId))
  if (matched.length) return matched
  if (list.length) return list
  return []
}

export function build1688SalesMetrics({ products, purchaseOrders, supplierAlerts, summary } = {}) {
  const gmv = summarize1688ProductGmv(products || [])
  const purchaseSummary = summarize1688PurchaseOrders(purchaseOrders || [])
  const alertCount = (supplierAlerts || []).filter(
    (a) => a.resolved !== true && a.isOpen !== false,
  ).length
  // 平台总览的 1688 销售额必须来自消费者订单聚合，不再使用商品表 gmv_1d。
  if (summary && typeof summary === 'object') {
    const netSales = Number(summary.net_sales ?? summary.paid_sales ?? 0)
    const paidOrders = Number(summary.paid_order_count ?? 0)
    return {
      revenue: netSales,
      orders: paidOrders,
      alerts: Number(summary.refund_order_count ?? 0) + Number(summary.sold_product_count ?? 0),
      revenueText: formatMoney(netSales),
    }
  }
  return {
    revenue: gmv.totalGmv,
    orders: gmv.soldCount,
    alerts: purchaseSummary.pending + alertCount,
    revenueText: gmv.totalGmvText,
  }
}
