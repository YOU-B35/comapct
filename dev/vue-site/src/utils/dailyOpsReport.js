import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { calcTaskStats } from '@/utils/operations'
import { OUTCOME_MAP } from '@/constants/opsFeedbackDemo'

function buildPlatformSummary(platform) {
  const parts = []
  if (platform.id === 'temu') {
    if (platform.pendingRestock) parts.push(`${platform.pendingRestock} 项补货`)
    if (platform.lossItems?.length) parts.push(`${platform.lossItems.length} 个亏损 SKU`)
  }
  if (platform.id === 'aliexpress') {
    if (platform.jitUnshippedCount) parts.push(`JIT 未发 ${platform.jitUnshippedCount}`)
    if (platform.warehousePendingCount) parts.push(`仓发待出 ${platform.warehousePendingCount}`)
    if (platform.pendingViolations) parts.push(`违规 ${platform.pendingViolations}`)
  }
  if (platform.id === 'walmart') {
    if (platform.wfsPendingCount) parts.push(`WFS ${platform.wfsPendingCount}`)
    if (platform.sellerPendingCount) parts.push(`自发货 ${platform.sellerPendingCount}`)
    if (platform.openListingCount) parts.push(`Listing ${platform.openListingCount}`)
  }
  if (platform.id === 'amazon') {
    if (platform.pendingMessages?.length) parts.push(`消息 ${platform.pendingMessages.length}`)
    if (platform.alertMetrics?.length) parts.push(`账户预警 ${platform.alertMetrics.length}`)
    if (platform.pendingReviews?.length) parts.push(`差评 ${platform.pendingReviews.length}`)
  }
  if (platform.id === '1688') {
    if (platform.pendingPayment?.length) parts.push(`待付款 ${platform.pendingPayment.length}`)
    if (platform.pendingShipment?.length) parts.push(`待发货 ${platform.pendingShipment.length}`)
    if (platform.supplierAlerts?.length) parts.push(`供应商 ${platform.supplierAlerts.length}`)
  }
  if (platform.id === 'dtc') {
    if (platform.pendingShipCount) parts.push(`待发货 ${platform.pendingShipCount}`)
  }
  return parts.length ? parts.join(' · ') : '今日运营正常'
}

/** 老板端：今日各平台运营快照 */
export function buildPlatformSnapshots(overview, platformSales = []) {
  const platforms = (overview?.platforms || []).filter((p) => p.bound)
  return platforms.map((platform) => {
    const sales = platformSales.find((row) => row.id === platform.id)
    const issueCount = platform.issueCount || 0
    return {
      id: platform.id,
      name: platform.name,
      owner: sales?.owner || '—',
      issueCount,
      alertLevel: issueCount >= 5 ? 'danger' : issueCount >= 2 ? 'warning' : 'success',
      revenueText: sales?.revenueText || '—',
      orders: sales?.orders ?? 0,
      storeCount: sales?.storeCount ?? 0,
      summary: buildPlatformSummary(platform),
      route: platform.route,
    }
  })
}

/** 老板端：各员工今日跟进概况 */
export function buildEmployeeFollowUps(employees = [], tasks = [], feedbacks = []) {
  const todayFeedbackByEmp = new Map()
  for (const fb of feedbacks) {
    todayFeedbackByEmp.set(fb.employeeId, (todayFeedbackByEmp.get(fb.employeeId) || 0) + 1)
  }

  return employees
    .filter((emp) => emp.status !== false)
    .map((emp) => {
      const empTasks = tasks.filter(
        (t) => t.employeeId === emp.id || t.assignee === emp.name,
      )
      const stats = calcTaskStats(empTasks)
      const issuePending = empTasks.filter(
        (t) => t.source === 'issue' && t.status !== '已完成',
      ).length
      const latestFeedback = feedbacks.find((f) => f.employeeId === emp.id)

      return {
        employeeId: emp.id,
        name: emp.name,
        role: emp.role,
        platforms: emp.platforms || [],
        totalTasks: stats.total,
        completed: stats.completed,
        inProgress: stats.inProgress,
        pending: stats.pending,
        overdue: stats.overdue,
        completionRate: stats.completionRate,
        issuePending,
        feedbackToday: todayFeedbackByEmp.get(emp.id) || 0,
        latestFeedback: latestFeedback?.feedback || '',
        latestFeedbackAt: latestFeedback?.submittedAt || '',
      }
    })
    .sort((a, b) => b.issuePending - a.issuePending || b.feedbackToday - a.feedbackToday)
}

/** 老板端：今日运营日报聚合 */
export function buildDailyOpsReport({ overview, platformSales, employees, tasks, feedbacks }) {
  const taskStats = calcTaskStats(tasks)
  const platformSnapshots = buildPlatformSnapshots(overview, platformSales)
  const employeeFollowUps = buildEmployeeFollowUps(employees, tasks, feedbacks)

  const resolvedFeedbacks = feedbacks.filter((f) => f.outcome === 'resolved').length
  const needHelpFeedbacks = feedbacks.filter((f) => f.outcome === 'need_help' || f.outcome === 'blocked').length

  return {
    date: nowUtc8DateString(),
    syncedAt: overview?.syncedAt || '',
    stats: {
      totalIssues: overview?.totalIssues ?? 0,
      platformCount: platformSnapshots.length,
      taskCompletionRate: taskStats.completionRate,
      tasksCompleted: taskStats.completed,
      tasksTotal: taskStats.total,
      feedbackCount: feedbacks.length,
      feedbackResolved: resolvedFeedbacks,
      feedbackNeedHelp: needHelpFeedbacks,
    },
    platformSnapshots,
    employeeFollowUps,
    feedbacks: feedbacks.map((fb) => ({
      ...fb,
      outcomeMeta: OUTCOME_MAP[fb.outcome] || OUTCOME_MAP.in_progress,
    })),
  }
}
