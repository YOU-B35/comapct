import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { TEMU_RESTOCK_STATUS_LABELS } from '@/constants/temuOps'
import { resolveTemuRestockStatus } from '@/api/temuRestock'
import { DTC_ORDER_STATUSES } from '@/constants/dtcOrders'
import { PURCHASE_ORDER_STATUSES, SUPPLIER_ALERT_TYPES } from '@/constants/alibaba1688'
import { buildDomesticPlatformSection } from '@/utils/domesticPlatform'
import { PDD_ISSUE_TYPES } from '@/constants/pddDemo'
import { TAOBAO_ISSUE_TYPES } from '@/constants/taobaoDemo'
import { DOUYIN_ISSUE_TYPES } from '@/constants/douyinDemo'
import { CHANNELS_ISSUE_TYPES } from '@/constants/channelsDemo'
import { attachAssignee, buildStoreAssigneeMap, resolveStoreAssignee } from '@/utils/storeAssignment'
import { formatMoneyDecimal } from '@/utils/format'

const JIT_UNSHIPPED = new Set(['待发货', '待揽收'])
const WAREHOUSE_UNSHIPPED = new Set(['待出库'])
const WAREHOUSE_SHIPPED = new Set(['已出库', '配送中', '已签收'])
const WFS_PENDING = new Set(['待拣货', '待发货'])
const WFS_SHIPPED = new Set(['已发货'])
const SELLER_PENDING = new Set(['待确认', '待发货'])
const SELLER_SHIPPED = new Set(['已发货'])

function todayKey() {
  return nowUtc8DateString()
}

function withStoreName(item, storeNameMap) {
  return {
    ...item,
    storeName: storeNameMap[item.storeId] || '—',
  }
}

function mapStoreSummaries(stores, assigneeMap) {
  return (stores || []).map((store) => ({
    storeId: store.id,
    storeName: store.storeName,
    assigneeName: resolveStoreAssignee(store.id, assigneeMap),
    assigneeRole: assigneeMap[store.id]?.role || '',
  }))
}

function buildTemuSection({ products = [], restockStatus, stores }, storeNameMap, assigneeMap) {
  const restockItems = products
    .filter(
      (p) =>
        p.restock.urgency === 'critical' ||
        p.restock.urgency === 'warning' ||
        resolveTemuRestockStatus(restockStatus, p),
    )
    .map((p) => {
      const tracked = resolveTemuRestockStatus(restockStatus, p)
      const status = tracked?.status || 'pending'
      const meta = TEMU_RESTOCK_STATUS_LABELS[status] || TEMU_RESTOCK_STATUS_LABELS.pending
      return attachAssignee(
        withStoreName(
          {
            storeId: p.storeId,
            sku: p.sku,
            name: p.name,
            spuId: p.spuId || '—',
            skcId: p.skcId || '—',
            skuId: p.skuId || '—',
            urgency: p.restock.urgencyLabel,
            suggestedRestock: p.restock.suggestedRestock,
            coverDays: p.restock.coverDays,
            restockStatus: status,
            restockStatusLabel: meta.label,
            restockStatusType: meta.type,
            note: tracked?.note || `建议补货 ${p.restock.suggestedRestock} 件`,
            isDone: status === 'done',
          },
          storeNameMap,
        ),
        p.storeId,
        assigneeMap,
      )
    })

  const lossItems = products
    .filter((p) => p.isLoss)
    .map((p) =>
      attachAssignee(
        withStoreName(
          {
            storeId: p.storeId,
            sku: p.sku,
            name: p.name,
            spuId: p.spuId || '—',
            skcId: p.skcId || '—',
            skuId: p.skuId || '—',
            sellingPrice: p.sellingPrice,
            unitProfit: p.unitProfit,
            listingStatus: p.listingStatusLabel,
          },
          storeNameMap,
        ),
        p.storeId,
        assigneeMap,
      ),
    )

  const storeSummaries = mapStoreSummaries(stores, assigneeMap)

  const storeGroups = storeSummaries.map((summary) => {
    const storeRestock = restockItems.filter((item) => item.storeId === summary.storeId)
    const storeLoss = lossItems.filter((item) => item.storeId === summary.storeId)
    return {
      ...summary,
      issueCount: storeRestock.filter((item) => !item.isDone).length + storeLoss.length,
      restockItems: storeRestock,
      lossItems: storeLoss,
    }
  })

  const pendingRestock = restockItems.filter((item) => !item.isDone).length

  return {
    id: 'temu',
    name: 'Temu',
    bound: (stores?.length || 0) > 0,
    issueCount: pendingRestock + lossItems.length,
    storeSummaries,
    storeGroups,
    restockItems,
    pendingRestock,
    doneRestock: restockItems.filter((item) => item.isDone).length,
    lossItems,
    route: '/boss/temu',
  }
}

function buildAliExpressSection({ orders, violations, stores }, storeNameMap, assigneeMap) {
  const jitOrders = orders.filter((o) => o.fulfillmentType === 'jit')
  const warehouseOrders = orders.filter((o) => o.fulfillmentType === 'warehouse')

  const mapJit = (o, extra) =>
    attachAssignee(
      withStoreName(
        {
          storeId: o.storeId,
          orderNo: o.orderNo,
          productName: o.productName,
          sku: o.sku,
          status: o.status,
          shipDeadline: o.shipDeadline,
          ...extra,
        },
        storeNameMap,
      ),
      o.storeId,
      assigneeMap,
    )

  const jitUnshipped = jitOrders
    .filter((o) => JIT_UNSHIPPED.has(o.status))
    .map((o) => mapJit(o, { isShipped: false }))

  const jitShipped = jitOrders
    .filter((o) => !JIT_UNSHIPPED.has(o.status) && o.status !== '已取消')
    .map((o) => mapJit(o, { isShipped: true }))

  const mapWarehouse = (o, extra) =>
    attachAssignee(
      withStoreName(
        {
          storeId: o.storeId,
          orderNo: o.orderNo,
          productName: o.productName,
          warehouseName: o.warehouseName,
          status: o.status,
          ...extra,
        },
        storeNameMap,
      ),
      o.storeId,
      assigneeMap,
    )

  const warehousePending = warehouseOrders
    .filter((o) => WAREHOUSE_UNSHIPPED.has(o.status))
    .map((o) => mapWarehouse(o, { isShippedToday: false }))

  const warehouseShipped = warehouseOrders
    .filter((o) => WAREHOUSE_SHIPPED.has(o.status))
    .map((o) => mapWarehouse(o, { isShippedToday: true }))

  const today = todayKey()
  const todayViolations = violations
    .filter((v) => String(v.violatedAt || '').startsWith(today))
    .map((v) =>
      attachAssignee(
        withStoreName(
          {
            storeId: v.storeId,
            id: v.id,
            typeLabel: v.typeLabel,
            orderNo: v.orderNo,
            fineAmount: v.fineAmount,
            currency: v.currency,
            confirmed: v.confirmed,
            appealStatus: v.appealStatus,
            appealStatusLabel: !v.confirmed
              ? '待确认'
              : v.appealStatus === 'appealed'
                ? '已申诉'
                : '未申诉',
            isAppealDone: v.confirmed,
          },
          storeNameMap,
        ),
        v.storeId,
        assigneeMap,
      ),
    )

  const pendingViolations = todayViolations.filter((v) => !v.isAppealDone).length
  const storeSummaries = mapStoreSummaries(stores, assigneeMap)

  const storeGroups = storeSummaries.map((summary) => {
    const sid = summary.storeId
    const storeJitUnshipped = jitUnshipped.filter((item) => item.storeId === sid)
    const storeJitShipped = jitShipped.filter((item) => item.storeId === sid)
    const storeWhPending = warehousePending.filter((item) => item.storeId === sid)
    const storeWhShipped = warehouseShipped.filter((item) => item.storeId === sid)
    const storeViolations = todayViolations.filter((item) => item.storeId === sid)
    return {
      ...summary,
      issueCount:
        storeJitUnshipped.length +
        storeWhPending.length +
        storeViolations.filter((v) => !v.isAppealDone).length,
      jitUnshipped: storeJitUnshipped,
      jitShipped: storeJitShipped,
      warehousePending: storeWhPending,
      warehouseShipped: storeWhShipped,
      todayViolations: storeViolations,
    }
  })

  return {
    id: 'aliexpress',
    name: 'AliExpress',
    bound: (stores?.length || 0) > 0,
    issueCount: jitUnshipped.length + warehousePending.length + pendingViolations,
    storeSummaries,
    storeGroups,
    jitUnshipped,
    jitShipped,
    jitUnshippedCount: jitUnshipped.length,
    jitShippedCount: jitShipped.length,
    warehousePending,
    warehouseShipped,
    warehousePendingCount: warehousePending.length,
    warehouseShippedCount: warehouseShipped.length,
    todayViolations,
    pendingViolations,
    route: '/boss/aliexpress',
  }
}

function buildWalmartSection({ orders, issues, stores }, storeNameMap, assigneeMap) {
  const wfsOrders = orders.filter((o) => o.fulfillmentType === 'wfs')
  const sellerOrders = orders.filter((o) => o.fulfillmentType === 'seller')

  const mapWfs = (o, extra) =>
    attachAssignee(
      withStoreName(
        {
          storeId: o.storeId,
          orderNo: o.orderNo,
          productName: o.productName,
          sku: o.sku,
          status: o.status,
          shipDeadline: o.shipDeadline,
          ...extra,
        },
        storeNameMap,
      ),
      o.storeId,
      assigneeMap,
    )

  const wfsPending = wfsOrders
    .filter((o) => WFS_PENDING.has(o.status))
    .map((o) => mapWfs(o, { isShipped: false }))

  const wfsShipped = wfsOrders
    .filter((o) => WFS_SHIPPED.has(o.status))
    .map((o) => mapWfs(o, { isShipped: true }))

  const mapSeller = (o, extra) =>
    attachAssignee(
      withStoreName(
        {
          storeId: o.storeId,
          orderNo: o.orderNo,
          productName: o.productName,
          sku: o.sku,
          status: o.status,
          shipDeadline: o.shipDeadline,
          ...extra,
        },
        storeNameMap,
      ),
      o.storeId,
      assigneeMap,
    )

  const sellerPending = sellerOrders
    .filter((o) => SELLER_PENDING.has(o.status))
    .map((o) => mapSeller(o, { isShipped: false }))

  const sellerShipped = sellerOrders
    .filter((o) => SELLER_SHIPPED.has(o.status))
    .map((o) => mapSeller(o, { isShipped: true }))

  const openIssues = issues
    .filter((item) => !item.resolved)
    .map((item) =>
      attachAssignee(
        withStoreName(
          {
            storeId: item.storeId,
            id: item.id,
            typeLabel: item.typeLabel || item.type,
            sku: item.sku,
            productName: item.productName,
            detail: item.detail,
            severity: item.severity,
            isResolved: item.resolved,
          },
          storeNameMap,
        ),
        item.storeId,
        assigneeMap,
      ),
    )

  const storeSummaries = mapStoreSummaries(stores, assigneeMap)

  const storeGroups = storeSummaries.map((summary) => {
    const sid = summary.storeId
    const storeWfsPending = wfsPending.filter((item) => item.storeId === sid)
    const storeWfsShipped = wfsShipped.filter((item) => item.storeId === sid)
    const storeSellerPending = sellerPending.filter((item) => item.storeId === sid)
    const storeSellerShipped = sellerShipped.filter((item) => item.storeId === sid)
    const storeIssues = openIssues.filter((item) => item.storeId === sid)
    return {
      ...summary,
      issueCount: storeWfsPending.length + storeSellerPending.length + storeIssues.length,
      wfsPending: storeWfsPending,
      wfsShipped: storeWfsShipped,
      sellerPending: storeSellerPending,
      sellerShipped: storeSellerShipped,
      openListingIssues: storeIssues,
    }
  })

  return {
    id: 'walmart',
    name: 'Walmart',
    bound: (stores?.length || 0) > 0,
    issueCount: wfsPending.length + sellerPending.length + openIssues.length,
    storeSummaries,
    storeGroups,
    wfsPending,
    wfsShipped,
    wfsPendingCount: wfsPending.length,
    wfsShippedCount: wfsShipped.length,
    sellerPending,
    sellerShipped,
    sellerPendingCount: sellerPending.length,
    sellerShippedCount: sellerShipped.length,
    openListingIssues: openIssues,
    openListingCount: openIssues.length,
    route: '/boss/walmart',
  }
}

function buildAmazonSection(payload, storeNameMap, assigneeMap) {
  const {
    buyerMessages = [],
    accountMetrics = [],
    reviews = [],
    coupons = [],
    shipments = [],
    cases = [],
    stores = [],
  } = payload

  const mapMsg = (m) =>
    attachAssignee(
      withStoreName(
        {
          storeId: m.storeId,
          id: m.id,
          buyerName: m.buyerName,
          subject: m.subject,
          preview: m.preview,
          receivedAt: m.receivedAt,
          status: m.status,
          isPending: m.status === 'pending',
        },
        storeNameMap,
      ),
      m.storeId,
      assigneeMap,
    )

  const pendingMessages = buyerMessages.filter((m) => m.status === 'pending').map(mapMsg)

  const mapMetric = (m) =>
    attachAssignee(
      withStoreName(
        {
          storeId: m.storeId,
          label: m.label,
          value: m.value,
          status: m.status,
          note: m.note,
          isCritical: m.status === 'critical',
          isWarning: m.status === 'warning',
        },
        storeNameMap,
      ),
      m.storeId,
      assigneeMap,
    )

  const alertMetrics = accountMetrics
    .filter((m) => m.status === 'critical' || m.status === 'warning')
    .map(mapMetric)

  const mapReview = (r) =>
    attachAssignee(
      withStoreName(
        {
          storeId: r.storeId,
          productName: r.productName,
          rating: r.rating,
          content: r.content,
          reviewedAt: r.reviewedAt,
          status: r.status,
          isPending: r.status === 'pending',
        },
        storeNameMap,
      ),
      r.storeId,
      assigneeMap,
    )

  const pendingReviews = reviews.filter((r) => r.status === 'pending').map(mapReview)

  const mapCoupon = (c) =>
    attachAssignee(
      withStoreName(
        {
          storeId: c.storeId,
          name: c.name,
          status: c.status,
          endAt: c.endAt,
          note: c.note,
          isAlert: ['expiring', 'expired', 'abnormal'].includes(c.status),
        },
        storeNameMap,
      ),
      c.storeId,
      assigneeMap,
    )

  const alertCoupons = coupons
    .filter((c) => ['expiring', 'expired', 'abnormal'].includes(c.status))
    .map(mapCoupon)

  const mapShipment = (s) =>
    attachAssignee(
      withStoreName(
        {
          storeId: s.storeId,
          shipmentId: s.shipmentId,
          productName: s.productName,
          unitsExpected: s.unitsExpected,
          unitsReceived: s.unitsReceived,
          status: s.status,
          note: s.note,
          isAlert: s.alertLevel === 'danger' || ['shortage', 'closed_no_stock'].includes(s.status),
        },
        storeNameMap,
      ),
      s.storeId,
      assigneeMap,
    )

  const alertShipments = shipments
    .filter(
      (s) => s.alertLevel === 'danger' || ['shortage', 'closed_no_stock'].includes(s.status),
    )
    .map(mapShipment)

  const mapCase = (c) =>
    attachAssignee(
      withStoreName(
        {
          storeId: c.storeId,
          caseId: c.caseId,
          subject: c.subject,
          preview: c.preview,
          lastReplyFrom: c.lastReplyFrom,
          lastReplyAt: c.lastReplyAt,
          hasNewReply: c.hasNewReply && !c.read,
        },
        storeNameMap,
      ),
      c.storeId,
      assigneeMap,
    )

  const newCaseReplies = cases.filter((c) => c.hasNewReply && !c.read).map(mapCase)

  const issueCount =
    pendingMessages.length +
    alertMetrics.length +
    pendingReviews.length +
    alertCoupons.length +
    alertShipments.length +
    newCaseReplies.length

  const storeSummaries = mapStoreSummaries(stores, assigneeMap)

  const storeGroups = storeSummaries.map((summary) => {
    const sid = summary.storeId
    const storeMessages = pendingMessages.filter((i) => i.storeId === sid)
    const storeMetrics = alertMetrics.filter((i) => i.storeId === sid)
    const storeReviews = pendingReviews.filter((i) => i.storeId === sid)
    const storeCoupons = alertCoupons.filter((i) => i.storeId === sid)
    const storeShipments = alertShipments.filter((i) => i.storeId === sid)
    const storeCases = newCaseReplies.filter((i) => i.storeId === sid)
    return {
      ...summary,
      issueCount:
        storeMessages.length +
        storeMetrics.length +
        storeReviews.length +
        storeCoupons.length +
        storeShipments.length +
        storeCases.length,
      pendingMessages: storeMessages,
      alertMetrics: storeMetrics,
      pendingReviews: storeReviews,
      alertCoupons: storeCoupons,
      alertShipments: storeShipments,
      newCaseReplies: storeCases,
    }
  })

  return {
    id: 'amazon',
    name: 'Amazon',
    bound: stores.length > 0,
    issueCount,
    storeSummaries,
    storeGroups,
    pendingMessages,
    alertMetrics,
    pendingReviews,
    alertCoupons,
    alertShipments,
    newCaseReplies,
    route: '/boss/amazon',
  }
}

function buildDtcSection({ orders, stores }, storeNameMap, assigneeMap) {
  const todayOrders = orders.map((o) => {
    const meta = DTC_ORDER_STATUSES[o.status] || DTC_ORDER_STATUSES.pending
    return attachAssignee(
      withStoreName(
        {
          storeId: o.storeId,
          orderNo: o.orderNo,
          productName: o.productName,
          sku: o.sku,
          quantity: o.quantity,
          amount: o.amount,
          currency: o.currency,
          status: o.status,
          statusLabel: meta.label,
          statusType: meta.type,
          orderedAt: o.orderedAt,
          shippedAt: o.shippedAt,
          customerCountry: o.customerCountry,
          isShipped: o.status !== 'pending',
        },
        storeNameMap,
      ),
      o.storeId,
      assigneeMap,
    )
  })

  const pendingShip = todayOrders.filter((o) => !o.isShipped)
  const storeSummaries = mapStoreSummaries(stores, assigneeMap)

  const storeGroups = storeSummaries.map((summary) => {
    const storeOrders = todayOrders.filter((item) => item.storeId === summary.storeId)
    return {
      ...summary,
      issueCount: storeOrders.filter((item) => !item.isShipped).length,
      todayOrders: storeOrders,
      todayOrderCount: storeOrders.length,
      shippedCount: storeOrders.filter((item) => item.isShipped).length,
      pendingShipCount: storeOrders.filter((item) => !item.isShipped).length,
    }
  })

  return {
    id: 'dtc',
    name: '独立站',
    bound: (stores?.length || 0) > 0,
    issueCount: pendingShip.length,
    storeSummaries,
    storeGroups,
    todayOrders,
    todayOrderCount: todayOrders.length,
    shippedCount: todayOrders.filter((o) => o.isShipped).length,
    pendingShipCount: pendingShip.length,
    pendingShip,
    route: '/boss/dtc',
  }
}

function build1688Section({ purchaseOrders, supplierAlerts, stores }, storeNameMap, assigneeMap) {
  const orders = (purchaseOrders || []).map((order) => {
    const meta = PURCHASE_ORDER_STATUSES[order.status] || PURCHASE_ORDER_STATUSES.pending_payment
    return attachAssignee(
      withStoreName(
        {
          storeId: order.storeId,
          orderNo: order.orderNo,
          productName: order.productName,
          sku: order.sku,
          supplierName: order.supplierName,
          quantity: order.quantity,
          amount: order.amount,
          linkedPlatform: order.linkedPlatform,
          status: order.status,
          statusLabel: meta.label,
          statusType: meta.type,
          expectedShipAt: order.expectedShipAt,
          payDeadline: order.payDeadline,
          isActionNeeded: ['pending_payment', 'pending_shipment'].includes(order.status),
        },
        storeNameMap,
      ),
      order.storeId,
      assigneeMap,
    )
  })

  const alerts = (supplierAlerts || [])
    .filter((alert) => alert.resolved !== true && alert.isOpen !== false)
    .map((alert) => {
      const meta = SUPPLIER_ALERT_TYPES[alert.type] || { label: alert.type, type: 'info' }
      return attachAssignee(
        withStoreName(
          {
            storeId: alert.storeId,
            type: alert.type,
            typeLabel: meta.label,
            typeTag: meta.type,
            supplierName: alert.supplierName,
            productName: alert.productName,
            detail: alert.detail || alert.message || '',
            severity: alert.severity || alert.level || 'medium',
            reportedAt: alert.reportedAt || alert.createdAt,
          },
          storeNameMap,
        ),
        alert.storeId,
        assigneeMap,
      )
    })

  const pendingPayment = orders.filter((o) => o.status === 'pending_payment')
  const pendingShipment = orders.filter((o) => o.status === 'pending_shipment')
  const pendingReceive = orders.filter((o) => o.status === 'pending_receive')
  const storeSummaries = mapStoreSummaries(stores, assigneeMap)

  const storeGroups = storeSummaries.map((summary) => {
    const sid = summary.storeId
    const storePendingPayment = pendingPayment.filter((item) => item.storeId === sid)
    const storePendingShipment = pendingShipment.filter((item) => item.storeId === sid)
    const storePendingReceive = pendingReceive.filter((item) => item.storeId === sid)
    const storeAlerts = alerts.filter((item) => item.storeId === sid)
    return {
      ...summary,
      issueCount:
        storePendingPayment.length + storePendingShipment.length + storeAlerts.length,
      pendingPayment: storePendingPayment,
      pendingShipment: storePendingShipment,
      pendingReceive: storePendingReceive,
      supplierAlerts: storeAlerts,
    }
  })

  return {
    id: '1688',
    name: '1688',
    bound: (stores?.length || 0) > 0,
    issueCount: pendingPayment.length + pendingShipment.length + alerts.length,
    storeSummaries,
    storeGroups,
    pendingPayment,
    pendingShipment,
    pendingReceive,
    supplierAlerts: alerts,
    route: '/boss/1688',
  }
}

export function buildOperationsOverview(payload) {
  const { temu, aliexpress, walmart, pdd, taobao, douyin, channels, amazon, dtc, alibaba1688, storeNameMaps, employees } = payload
  const assigneeMap = buildStoreAssigneeMap(employees)

  const platforms = [
    buildTemuSection(temu, storeNameMaps.temu, assigneeMap),
    buildAliExpressSection(aliexpress, storeNameMaps.aliexpress, assigneeMap),
    buildWalmartSection(walmart, storeNameMaps.walmart, assigneeMap),
    buildDomesticPlatformSection(
      { id: 'pdd', name: '拼多多', route: '/boss/pdd', issueTypeMap: PDD_ISSUE_TYPES },
      pdd,
      storeNameMaps.pdd,
      assigneeMap,
    ),
    buildDomesticPlatformSection(
      { id: 'taobao', name: '淘宝', route: '/boss/taobao', issueTypeMap: TAOBAO_ISSUE_TYPES },
      taobao,
      storeNameMaps.taobao,
      assigneeMap,
    ),
    buildDomesticPlatformSection(
      { id: 'douyin', name: '抖音', route: '/boss/douyin', issueTypeMap: DOUYIN_ISSUE_TYPES },
      douyin,
      storeNameMaps.douyin,
      assigneeMap,
    ),
    buildDomesticPlatformSection(
      { id: 'channels', name: '视频号', route: '/boss/channels', issueTypeMap: CHANNELS_ISSUE_TYPES },
      channels,
      storeNameMaps.channels,
      assigneeMap,
    ),
    buildAmazonSection(amazon, storeNameMaps.amazon, assigneeMap),
    build1688Section(alibaba1688, storeNameMaps['1688'], assigneeMap),
    buildDtcSection(dtc, storeNameMaps.dtc, assigneeMap),
  ]

  const totalIssues = platforms.reduce((sum, p) => sum + p.issueCount, 0)

  return {
    platforms,
    totalIssues,
    syncedAt: nowUtc8String(),
  }
}

export function formatOrderAmount(amount, currency) {
  return `${formatMoneyDecimal(amount)} ${currency}`
}
