import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { AMAZON_DAILY_STEPS } from '@/constants/amazonDaily'

function hoursSince(dateStr) {
  if (!dateStr) return 0
  const ms = Date.now() - new Date(dateStr.replace(' ', 'T')).getTime()
  return Math.max(0, ms / 3600000)
}

export function summarizeBuyerMessages(messages = []) {
  const pending = messages.filter((m) => m.status === 'pending')
  const urgent = pending.filter((m) => {
    const elapsed = hoursSince(m.receivedAt)
    return elapsed >= (m.slaHours || 24) * 0.75
  })
  return {
    total: messages.length,
    pending: pending.length,
    urgent: urgent.length,
    replied: messages.filter((m) => m.status === 'replied').length,
  }
}

export function summarizeAccountHealth(metrics = []) {
  const critical = metrics.filter((m) => m.status === 'critical')
  const warning = metrics.filter((m) => m.status === 'warning')
  return {
    total: metrics.length,
    critical: critical.length,
    warning: warning.length,
    normal: metrics.filter((m) => m.status === 'normal').length,
    hasAlert: critical.length + warning.length > 0,
  }
}

export function summarizeReviews(reviews = []) {
  const pending = reviews.filter((r) => r.status === 'pending')
  const low = pending.filter((r) => r.rating <= 3)
  return {
    total: reviews.length,
    pending: pending.length,
    lowStar: low.length,
    byRating: {
      1: pending.filter((r) => r.rating === 1).length,
      2: pending.filter((r) => r.rating === 2).length,
      3: pending.filter((r) => r.rating === 3).length,
    },
  }
}

export function summarizeCoupons(coupons = []) {
  const alerts = coupons.filter((c) =>
    ['expiring', 'expired', 'abnormal'].includes(c.status),
  )
  return {
    total: coupons.length,
    active: coupons.filter((c) => c.status === 'active').length,
    expiring: coupons.filter((c) => c.status === 'expiring').length,
    expired: coupons.filter((c) => c.status === 'expired').length,
    abnormal: coupons.filter((c) => c.status === 'abnormal').length,
    alerts: alerts.length,
  }
}

export function summarizeSellerNews(news = []) {
  const high = news.filter((n) => n.importance === 'high')
  return {
    total: news.length,
    highPriority: high.length,
    today: news.filter((n) => {
      const today = nowUtc8DateString()
      return String(n.publishedAt || '').startsWith(today)
    }).length,
  }
}

export function summarizeShipments(shipments = []) {
  const alerts = shipments.filter(
    (s) => s.alertLevel === 'danger' || ['shortage', 'closed_no_stock'].includes(s.status),
  )
  return {
    total: shipments.length,
    inTransit: shipments.filter((s) => s.status === 'in_transit').length,
    delivered: shipments.filter((s) => s.status === 'delivered').length,
    shortage: shipments.filter((s) => s.status === 'shortage').length,
    closedNoStock: shipments.filter((s) => s.status === 'closed_no_stock').length,
    alerts: alerts.length,
  }
}

export function summarizeCases(cases = []) {
  const newReplies = cases.filter((c) => c.hasNewReply && !c.read)
  const pendingReply = cases.filter((c) => c.status === 'pending_reply')
  return {
    total: cases.length,
    newReplies: newReplies.length,
    pendingReply: pendingReply.length,
    open: cases.filter((c) => c.status === 'open').length,
  }
}

/** 各工作流步骤待办数 */
export function buildAmazonDailyChecklist(payload = {}) {
  const {
    buyerMessages = [],
    accountMetrics = [],
    reviews = [],
    coupons = [],
    sellerNews = [],
    shipments = [],
    cases = [],
  } = payload

  const msg = summarizeBuyerMessages(buyerMessages)
  const account = summarizeAccountHealth(accountMetrics)
  const rev = summarizeReviews(reviews)
  const cpn = summarizeCoupons(coupons)
  const news = summarizeSellerNews(sellerNews)
  const shp = summarizeShipments(shipments)
  const cs = summarizeCases(cases)

  const counts = {
    messages: msg.pending,
    account: account.critical + account.warning,
    reviews: rev.pending,
    coupons: cpn.alerts,
    news: news.highPriority,
    shipments: shp.alerts,
    cases: cs.newReplies,
  }

  return AMAZON_DAILY_STEPS.map((step) => ({
    ...step,
    count: counts[step.key] || 0,
    urgent: step.key === 'messages' ? msg.urgent > 0 : counts[step.key] > 0,
  }))
}

export function summarizeAmazonDaily(payload = {}) {
  const checklist = buildAmazonDailyChecklist(payload)
  const totalPending = checklist.reduce((sum, item) => sum + item.count, 0)
  const completedSteps = checklist.filter((item) => item.count === 0).length

  return {
    checklist,
    totalPending,
    completedSteps,
    totalSteps: checklist.length,
    progressText: `${completedSteps}/${checklist.length} 项已清空`,
    progressPercent: Math.round((completedSteps / checklist.length) * 100),
  }
}

export function countAmazonPendingAlerts(payload = {}) {
  return summarizeAmazonDaily(payload).totalPending
}

export function summarizeAmazonByStore(payload, stores = []) {
  const {
    buyerMessages = [],
    accountMetrics = [],
    reviews = [],
    coupons = [],
    shipments = [],
    cases = [],
  } = payload

  return stores.map((store) => {
    const sid = store.id
    const slice = {
      buyerMessages: buyerMessages.filter((i) => i.storeId === sid),
      accountMetrics: accountMetrics.filter((i) => i.storeId === sid),
      reviews: reviews.filter((i) => i.storeId === sid),
      coupons: coupons.filter((i) => i.storeId === sid),
      shipments: shipments.filter((i) => i.storeId === sid),
      cases: cases.filter((i) => i.storeId === sid),
    }
    const daily = summarizeAmazonDaily(slice)
    return { store, ...daily }
  })
}

/** 运营总览用：单店各板块待办行 */
export function amazonStoreAlertRows(payload, storeId) {
  const filter = (arr) => (arr || []).filter((i) => i.storeId === storeId)
  const msgs = filter(payload.buyerMessages)
  const metrics = filter(payload.accountMetrics)
  const revs = filter(payload.reviews)
  const cpns = filter(payload.coupons)
  const shps = filter(payload.shipments)
  const cs = filter(payload.cases)

  return {
    pendingMessages: msgs.filter((m) => m.status === 'pending'),
    criticalMetrics: metrics.filter((m) => m.status === 'critical'),
    warningMetrics: metrics.filter((m) => m.status === 'warning'),
    pendingReviews: revs.filter((r) => r.status === 'pending'),
    alertCoupons: cpns.filter((c) => ['expiring', 'expired', 'abnormal'].includes(c.status)),
    alertShipments: shps.filter(
      (s) => s.alertLevel === 'danger' || ['shortage', 'closed_no_stock'].includes(s.status),
    ),
    newCaseReplies: cs.filter((c) => c.hasNewReply && !c.read),
  }
}
