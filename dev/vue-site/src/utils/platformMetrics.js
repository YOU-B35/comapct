import { buildStoreAssigneeMap } from '@/utils/storeAssignment'
import { summarizeTemuProducts } from '@/utils/temuStore'
import { summarizeAliExpressOrders } from '@/utils/aliexpress'
import { summarizeWalmartOrders, summarizeWalmartListings } from '@/utils/walmart'
import { summarizeDomesticOrders, summarizeDomesticIssues } from '@/utils/domesticPlatform'
import { countAmazonPendingAlerts } from '@/utils/amazon'
import { build1688SalesMetrics } from '@/utils/alibaba1688'
import { formatMoney } from '@/utils/format'

function primaryOwner(employees, platformKey, assigneeMap, storeIds) {
  const counts = {}
  for (const storeId of storeIds) {
    const name = assigneeMap[storeId]?.name
    if (name) counts[name] = (counts[name] || 0) + 1
  }
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]
  if (top) return top[0]

  const fallback = employees.find(
    (employee) =>
      employee.status !== false && (employee.platforms || []).includes(platformKey),
  )
  return fallback?.name || '—'
}

export function buildPlatformSalesRows(payload) {
  const { temu, aliexpress, walmart, pdd, taobao, douyin, channels, amazon, alibaba1688, dtc, employees = [] } = payload
  const assigneeMap = buildStoreAssigneeMap(employees)
  const rows = []

  if (temu?.stores?.length) {
    const summary = temu.products?.length
      ? summarizeTemuProducts(temu.products)
      : {
          dailyRevenue: 0,
          dailySales: 0,
          lossCount: 0,
          restockCount: 0,
          dailyRevenueText: formatMoney(0),
        }
    const storeIds = temu.stores.map((store) => store.id)
    rows.push({
      id: 'temu',
      name: 'Temu',
      owner: primaryOwner(employees, 'temu', assigneeMap, storeIds),
      revenue: summary.dailyRevenue,
      orders: summary.dailySales,
      alerts: summary.lossCount + summary.restockCount,
      storeCount: storeIds.length,
      revenueText: summary.dailyRevenueText || formatMoney(summary.dailyRevenue),
    })
  }

  if (aliexpress?.stores?.length) {
    const summary = aliexpress.orders?.length
      ? summarizeAliExpressOrders(aliexpress.orders)
      : { totalAmount: 0, total: 0, pending: 0, totalAmountText: formatMoney(0) }
    const storeIds = aliexpress.stores.map((store) => store.id)
    const pending = summary.pending
    rows.push({
      id: 'aliexpress',
      name: 'AliExpress',
      owner: primaryOwner(employees, 'aliexpress', assigneeMap, storeIds),
      revenue: summary.totalAmount,
      orders: summary.total,
      alerts: pending,
      storeCount: storeIds.length,
      revenueText: summary.totalAmountText,
    })
  }

  if (walmart?.stores?.length) {
    const orderSummary = summarizeWalmartOrders(walmart.orders || [])
    const issueSummary = summarizeWalmartListings(walmart.issues || [])
    const storeIds = walmart.stores.map((store) => store.id)
    rows.push({
      id: 'walmart',
      name: 'Walmart',
      owner: primaryOwner(employees, 'walmart', assigneeMap, storeIds),
      revenue: orderSummary.totalAmount,
      orders: orderSummary.total,
      alerts: orderSummary.pending + issueSummary.open,
      storeCount: storeIds.length,
      revenueText: orderSummary.totalAmountText,
    })
  }

  for (const item of [
    { key: 'pdd', name: '拼多多', data: pdd },
    { key: 'taobao', name: '淘宝', data: taobao },
    { key: 'douyin', name: '抖音', data: douyin },
    { key: 'channels', name: '视频号', data: channels },
  ]) {
    if (!item.data?.stores?.length) continue
    const orderSummary = summarizeDomesticOrders(item.data.orders || [])
    const issueSummary = summarizeDomesticIssues(item.data.issues || [])
    const storeIds = (item.data.stores || []).map((store) => store.id)
    rows.push({
      id: item.key,
      name: item.name,
      owner: primaryOwner(employees, item.key, assigneeMap, storeIds),
      revenue: orderSummary.totalAmount,
      orders: orderSummary.total,
      alerts: orderSummary.pending + issueSummary.open,
      storeCount: storeIds.length,
      revenueText: orderSummary.totalAmountText,
    })
  }

  if (amazon?.stores?.length) {
    const alerts = countAmazonPendingAlerts(amazon)
    const storeIds = (amazon.stores || []).map((store) => store.id)
    const critical = (amazon.accountMetrics || []).filter((m) => m.status === 'critical').length
    rows.push({
      id: 'amazon',
      name: 'Amazon',
      owner: primaryOwner(employees, 'amazon', assigneeMap, storeIds),
      revenue: 0,
      orders: (amazon.buyerMessages || []).filter((m) => m.status === 'replied').length,
      alerts,
      storeCount: storeIds.length,
      revenueText: critical ? `${critical} 项爆红` : '今日巡检',
    })
  }

  if (alibaba1688?.stores?.length) {
    const metrics = build1688SalesMetrics({
      products: alibaba1688.products || [],
      purchaseOrders: alibaba1688.purchaseOrders || [],
      supplierAlerts: alibaba1688.supplierAlerts || [],
      summary: alibaba1688.summary,
    })
    const storeIds = alibaba1688.stores.map((store) => store.id)
    rows.push({
      id: '1688',
      name: '1688',
      owner: primaryOwner(employees, '1688', assigneeMap, storeIds),
      revenue: metrics.revenue,
      orders: metrics.orders,
      alerts: metrics.alerts,
      storeCount: storeIds.length,
      revenueText: metrics.revenueText,
    })
  }

  if (dtc?.stores?.length) {
    const orders = dtc.orders || []
    const revenue = orders.reduce((sum, order) => sum + (order.amount || 0), 0)
    const pending = orders.filter((order) => order.status === 'pending').length
    const storeIds = (dtc.stores || []).map((store) => store.id)
    rows.push({
      id: 'dtc',
      name: '独立站',
      owner: primaryOwner(employees, 'shopify', assigneeMap, storeIds),
      revenue,
      orders: orders.length,
      alerts: pending,
      storeCount: storeIds.length,
      revenueText: formatMoney(revenue),
    })
  }

  return rows
}
