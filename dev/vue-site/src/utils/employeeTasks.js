import { demoPlanTasks } from '@/utils/operations'
import { filterTasksForAuth } from '@/utils/operations'
import { fetchAssignedTasksForCenter } from '@/api/assignedTasks'

const PLATFORM_LABELS = {
  temu: 'Temu',
  aliexpress: 'AliExpress',
  amazon: 'Amazon',
  walmart: 'Walmart',
  pdd: '拼多多',
  douyin: '抖音',
  channels: '视频号',
  '1688': '1688',
  dtc: '独立站',
}

const EMPLOYEE_ROUTES = {
  temu: '/employee/temu',
  aliexpress: '/employee/aliexpress',
  amazon: '/employee/amazon',
  walmart: '/employee/walmart',
  pdd: '/employee/pdd',
  douyin: '/employee/douyin',
  channels: '/employee/channels',
  '1688': '/employee/1688',
  dtc: '/employee/dtc',
}

const PRIORITY_WEIGHT = { high: 0, medium: 1, low: 2 }
const STATUS_WEIGHT = { 已逾期: 0, 进行中: 1, 待处理: 2, 已完成: 9 }

function employeePlatformKeys(auth) {
  const keys = new Set(
    auth?.backendLinked
      ? (auth.platforms || [])
      : (auth?.employee?.platforms || []),
  )
  if (keys.has('dtc') || keys.has('shopify') || keys.has('wordpress')) {
    keys.delete('shopify')
    keys.delete('wordpress')
    keys.add('dtc')
  }
  return keys
}

function isPlatformVisible(platformId, auth) {
  if (!auth || auth.isBoss) return true
  return employeePlatformKeys(auth).has(platformId)
}

function isIssueVisible(item, auth) {
  if (!auth || auth.isBoss) return true
  const assigned = auth.employee?.assignedStoreIds || []
  if (assigned.length) return assigned.includes(item.storeId)
  return true
}

function makeIssueTask({
  id,
  platformKey,
  category,
  priority,
  title,
  detail,
  storeName,
  assignee,
  due = '今天 18:00',
}) {
  return {
    id,
    source: 'issue',
    title,
    detail: detail || '',
    platform: PLATFORM_LABELS[platformKey] || platformKey,
    platformKey,
    category,
    priority,
    status: '待处理',
    progress: 0,
    due,
    storeName: storeName || '—',
    assignee: assignee || '未分配',
    route: EMPLOYEE_ROUTES[platformKey] || '',
    updatedAt: new Date().toISOString().replace('T', ' ').slice(0, 16),
  }
}

function collectTemuTasks(platform, auth, tasks) {
  for (const item of platform.restockItems || []) {
    if (!isIssueVisible(item, auth) || item.isDone) continue
    const priority = item.urgency === 'critical' || item.restockStatus === 'critical' ? 'high' : 'medium'
    tasks.push(
      makeIssueTask({
        id: `issue_temu_restock_${item.storeId}_${item.sku}`,
        platformKey: 'temu',
        category: '库存',
        priority,
        title: `补货跟进：${item.name}`,
        detail: `${item.storeName} · 覆盖 ${item.coverDays ?? '—'} 天 · ${item.note || item.restockStatusLabel}`,
        storeName: item.storeName,
        assignee: item.assigneeName,
        due: priority === 'high' ? '今天 18:00' : '今天 21:00',
      }),
    )
  }

  for (const item of platform.lossItems || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_temu_loss_${item.storeId}_${item.sku}`,
        platformKey: 'temu',
        category: '定价',
        priority: 'high',
        title: `亏损 SKU 处理：${item.name}`,
        detail: `${item.storeName} · 单件利润 ${item.unitProfit ?? '—'} · ${item.listingStatus || '在售'}`,
        storeName: item.storeName,
        assignee: item.assigneeName,
      }),
    )
  }
}

function collectAliExpressTasks(platform, auth, tasks) {
  for (const item of platform.jitUnshipped || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_ae_jit_${item.storeId}_${item.orderNo}`,
        platformKey: 'aliexpress',
        category: '订单',
        priority: 'high',
        title: `JIT 未发货：${item.orderNo}`,
        detail: `${item.storeName} · ${item.productName} · 截止 ${item.shipDeadline || '—'}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
        due: '今天 17:00',
      }),
    )
  }

  for (const item of platform.warehousePending || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_ae_wh_${item.storeId}_${item.orderNo}`,
        platformKey: 'aliexpress',
        category: '订单',
        priority: 'medium',
        title: `仓发待出库：${item.orderNo}`,
        detail: `${item.storeName} · ${item.productName} · ${item.warehouseName || '—'}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
      }),
    )
  }

  for (const item of platform.todayViolations || []) {
    if (!isIssueVisible(item, auth) || item.isAppealDone) continue
    tasks.push(
      makeIssueTask({
        id: `issue_ae_viol_${item.storeId}_${item.id}`,
        platformKey: 'aliexpress',
        category: '合规',
        priority: 'high',
        title: `违规待确认：${item.typeLabel}`,
        detail: `${item.storeName} · 订单 ${item.orderNo} · 罚款 ${item.fineAmount ?? '—'} ${item.currency || ''}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
      }),
    )
  }
}

function collectDomesticTasks(platformKey, platform, auth, tasks) {
  for (const item of platform.pendingOrders || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_${platformKey}_order_${item.storeId}_${item.orderNo}`,
        platformKey,
        category: '订单',
        priority: 'high',
        title: `待处理订单：${item.orderNo}`,
        detail: `${item.storeName} · ${item.productName} · ${item.status}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
        due: '今天 18:00',
      }),
    )
  }

  for (const item of platform.openIssues || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_${platformKey}_alert_${item.storeId}_${item.id}`,
        platformKey,
        category: '运营',
        priority: item.severity === 'high' ? 'high' : 'medium',
        title: `运营预警：${item.typeLabel || item.type}`,
        detail: `${item.storeName} · ${item.sku} · ${item.detail || item.productName}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
      }),
    )
  }
}

function collectWalmartTasks(platform, auth, tasks) {
  for (const item of platform.wfsPending || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_wm_wfs_${item.storeId}_${item.orderNo}`,
        platformKey: 'walmart',
        category: '订单',
        priority: 'high',
        title: `WFS 待处理：${item.orderNo}`,
        detail: `${item.storeName} · ${item.productName} · ${item.status}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
        due: '今天 18:00',
      }),
    )
  }

  for (const item of platform.sellerPending || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_wm_seller_${item.storeId}_${item.orderNo}`,
        platformKey: 'walmart',
        category: '订单',
        priority: 'medium',
        title: `自发货待处理：${item.orderNo}`,
        detail: `${item.storeName} · ${item.productName} · ${item.status}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
      }),
    )
  }

  for (const item of platform.openListingIssues || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_wm_listing_${item.storeId}_${item.id}`,
        platformKey: 'walmart',
        category: 'Listing',
        priority: item.severity === 'high' ? 'high' : 'medium',
        title: `Listing 问题：${item.typeLabel || item.type}`,
        detail: `${item.storeName} · ${item.sku} · ${item.detail || item.productName}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
      }),
    )
  }
}

function collectAmazonTasks(platform, auth, tasks) {
  for (const item of platform.pendingMessages || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_amz_msg_${item.storeId}_${item.id}`,
        platformKey: 'amazon',
        category: '客服',
        priority: 'high',
        title: `买家消息待回复：${item.subject}`,
        detail: `${item.storeName} · ${item.buyerName} · ${item.preview || ''}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
        due: '今天 23:59',
      }),
    )
  }

  for (const item of platform.alertMetrics || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_amz_metric_${item.storeId}_${item.label}`,
        platformKey: 'amazon',
        category: '账户',
        priority: item.isCritical ? 'high' : 'medium',
        title: `账户预警：${item.label}`,
        detail: `${item.storeName} · 当前 ${item.value} · ${item.note || ''}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
      }),
    )
  }

  for (const item of platform.pendingReviews || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_amz_review_${item.storeId}_${item.reviewedAt}`,
        platformKey: 'amazon',
        category: '客服',
        priority: 'medium',
        title: `差评跟进：${item.productName}`,
        detail: `${item.storeName} · ${item.rating} 星 · ${item.content || ''}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
      }),
    )
  }

  for (const item of platform.alertCoupons || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_amz_coupon_${item.storeId}_${item.name}`,
        platformKey: 'amazon',
        category: '促销',
        priority: 'medium',
        title: `优惠券异常：${item.name}`,
        detail: `${item.storeName} · ${item.status} · ${item.note || ''}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
      }),
    )
  }

  for (const item of platform.alertShipments || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_amz_ship_${item.storeId}_${item.shipmentId}`,
        platformKey: 'amazon',
        category: '货件',
        priority: 'high',
        title: `货件预警：${item.shipmentId}`,
        detail: `${item.storeName} · ${item.productName} · ${item.note || item.status}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
      }),
    )
  }

  for (const item of platform.newCaseReplies || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_amz_case_${item.storeId}_${item.caseId}`,
        platformKey: 'amazon',
        category: 'Case',
        priority: 'high',
        title: `Case 新回复：${item.subject}`,
        detail: `${item.storeName} · ${item.preview || ''}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
      }),
    )
  }
}

function collect1688Tasks(platform, auth, tasks) {
  for (const item of platform.pendingPayment || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_1688_pay_${item.storeId}_${item.orderNo}`,
        platformKey: '1688',
        category: '采购',
        priority: 'high',
        title: `采购单待付款：${item.orderNo}`,
        detail: `${item.storeName} · ${item.productName} · ${item.supplierName}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
        due: item.payDeadline ? String(item.payDeadline).slice(11, 16) : '今天 17:30',
      }),
    )
  }

  for (const item of platform.pendingShipment || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_1688_ship_${item.storeId}_${item.orderNo}`,
        platformKey: '1688',
        category: '采购',
        priority: 'medium',
        title: `采购单待发货：${item.orderNo}`,
        detail: `${item.storeName} · ${item.supplierName} · 预计 ${item.expectedShipAt || '—'}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
      }),
    )
  }

  for (const item of platform.supplierAlerts || []) {
    if (!isIssueVisible(item, auth)) continue
    const alertType = String(item.type || '')
    const isOpsAlert = alertType === 'delay' || alertType === 'stockout'
    tasks.push(
      makeIssueTask({
        id: `issue_1688_alert_${item.storeId}_${item.type}_${item.supplierName}_${item.relatedOrderNo || item.orderNo || ''}`,
        platformKey: '1688',
        category: '供应商',
        priority: item.severity === 'high' || isOpsAlert ? 'high' : 'medium',
        title: `供应商预警：${item.typeLabel || item.type}`,
        detail: `${item.storeName} · ${item.supplierName} · ${item.detail || item.message || ''}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
      }),
    )
  }
}

function collectDtcTasks(platform, auth, tasks) {
  for (const item of platform.pendingShip || []) {
    if (!isIssueVisible(item, auth)) continue
    tasks.push(
      makeIssueTask({
        id: `issue_dtc_order_${item.storeId}_${item.orderNo}`,
        platformKey: 'dtc',
        category: '订单',
        priority: 'high',
        title: `独立站待发货：${item.orderNo}`,
        detail: `${item.storeName} · ${item.productName} · ${item.customerCountry || '—'}`,
        assignee: item.assigneeName,
        storeName: item.storeName,
        due: '今天 18:00',
      }),
    )
  }
}

const PLATFORM_COLLECTORS = {
  temu: collectTemuTasks,
  aliexpress: collectAliExpressTasks,
  walmart: collectWalmartTasks,
  pdd: (platform, auth, tasks) => collectDomesticTasks('pdd', platform, auth, tasks),
  douyin: (platform, auth, tasks) => collectDomesticTasks('douyin', platform, auth, tasks),
  channels: (platform, auth, tasks) => collectDomesticTasks('channels', platform, auth, tasks),
  amazon: collectAmazonTasks,
  '1688': collect1688Tasks,
  dtc: collectDtcTasks,
}

/** 从运营总览各平台问题生成员工待办 */
export function buildIssueTasksFromOverview(overview, auth) {
  const tasks = []
  const platforms = overview?.platforms || []

  for (const platform of platforms) {
    if (!platform.bound || !isPlatformVisible(platform.id, auth)) continue
    const collector = PLATFORM_COLLECTORS[platform.id]
    if (collector) collector(platform, auth, tasks)
  }

  return tasks
}

function sortTasks(tasks) {
  return [...tasks].sort((a, b) => {
    const pw = (PRIORITY_WEIGHT[a.priority] ?? 2) - (PRIORITY_WEIGHT[b.priority] ?? 2)
    if (pw !== 0) return pw
    const sw = (STATUS_WEIGHT[a.status] ?? 5) - (STATUS_WEIGHT[b.status] ?? 5)
    if (sw !== 0) return sw
    return String(a.platform).localeCompare(String(b.platform), 'zh-CN')
  })
}

/** 合并运营预警任务与计划任务，供员工任务中心使用 */
export async function buildEmployeeTaskCenter(overview, auth, employees = []) {
  const issueTasks = buildIssueTasksFromOverview(overview, auth)
  const planTasks = filterTasksForAuth(employees, auth).map((task) => ({
    ...task,
    source: task.source || 'plan',
  }))
  const assignedTasks = await fetchAssignedTasksForCenter(auth, employees)

  const issueKeys = new Set(issueTasks.map((t) => `${t.platformKey}:${t.category}`))
  const filteredPlan = planTasks.filter((task) => {
    if (task.status === '已完成') return false
    const key = `${task.platformKey}:${task.category}`
    if (task.source === 'plan' && issueKeys.has(key) && issueTasks.length > 3) {
      return false
    }
    return true
  })

  const byId = new Map()
  for (const task of [...issueTasks, ...filteredPlan, ...assignedTasks]) {
    byId.set(String(task.id), task)
  }
  return sortTasks([...byId.values()])
}

/** 按平台分组任务 */
export function groupEmployeeTasksByPlatform(tasks = []) {
  const map = new Map()

  for (const task of tasks) {
    const key = task.platformKey || task.platform || 'other'
    if (!map.has(key)) {
      map.set(key, {
        platformKey: key,
        platform: task.platform || key,
        route: task.route || EMPLOYEE_ROUTES[key] || '',
        tasks: [],
        pending: 0,
        high: 0,
      })
    }
    const group = map.get(key)
    group.tasks.push(task)
    if (task.status !== '已完成') group.pending += 1
    if (task.priority === 'high' && task.status !== '已完成') group.high += 1
  }

  return [...map.values()].sort((a, b) => b.pending - a.pending || b.high - a.high)
}

/** 老板端：全平台预警 + 计划任务 + 管理员分配任务 */
export async function buildBossTaskCenter(overview, auth, employees = []) {
  const bossAuth = { isBoss: true, backendLinked: auth?.backendLinked }
  const nameToId = Object.fromEntries(employees.map((emp) => [emp.name, emp.id]))
  const issueTasks = buildIssueTasksFromOverview(overview, bossAuth).map((task) => ({
    ...task,
    employeeId: nameToId[task.assignee] || '',
  }))
  const planTasks = demoPlanTasks(auth).map((task) => ({ ...task, source: 'plan' }))
  const assignedTasks = await fetchAssignedTasksForCenter(bossAuth, employees)

  const byId = new Map()
  for (const task of [...issueTasks, ...planTasks, ...assignedTasks]) {
    byId.set(String(task.id), task)
  }
  return sortTasks([...byId.values()])
}

/** Boss 使用全量任务；员工使用聚合任务 */
export async function buildTaskCenterForAuth(overview, auth, employees = []) {
  if (!auth || auth.isBoss) {
    return buildBossTaskCenter(overview, auth, employees)
  }
  return buildEmployeeTaskCenter(overview, auth, employees)
}

export { PLATFORM_LABELS, EMPLOYEE_ROUTES }
