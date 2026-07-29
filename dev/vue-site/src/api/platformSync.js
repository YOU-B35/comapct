import { fetchAllPlatformStores } from './platformAccounts'
import {
  canUseTemuBackend,
  fetchTemuOperationalData,
  fetchTemuSessionStatus,
  fetchTemuStores,
  fetchTemuSyncStatus,
  formatCrawlError,
  openTemuSellerLogin,
  pollTemuSessionUntilReady,
  pollTemuProfileIdle,
  refreshTemuDataWithCrawl,
} from './temuApi'
import {
  canUseAliExpressBackend,
  refreshAliExpressDataWithCrawl,
  fetchTodayAliExpressOrdersFromApi,
  loadAliExpressViolationsFromApi,
  fetchAliExpressOperationalData,
} from './aliexpressApi'
import {
  canUseAmazonBackend,
  fetchAmazonDailyFromBackend,
  fetchAmazonInsightsFromBackend,
  refreshAmazonAccountHealth,
} from './amazon'
import { fetchAmazonIntegrationStatus } from './agentApi'
import { probeLocalZiniao } from '@/utils/ziniaoProbe'
import { probeLocalAgent } from '@/utils/agentProbe'
import { autoSyncCompetitorTargetsOnPlatformRefresh } from '@/api/temuCompetitorsApi'
import { fetchAmazonStores } from './platformAccounts'
import { touchPlatformCrawlCooldown } from './platformCrawlCooldown'
import {
  createPlatformSyncBatchOptions,
  formatCooldownRemaining,
  getCooldownRemainingMs,
  hasSuccessfulSyncItems,
  isPlatformCrawlInCooldown,
  markPlatformCrawlOnSuccess,
} from '@/utils/platformSyncCooldown'
import { scopeStores } from '@/utils/scope'
import {
  DOMESTIC_PLATFORM_OPTIONS,
  DTC_PLATFORM_OPTIONS,
  MARKETPLACE_PLATFORM_OPTIONS,
} from '@/constants/platforms'

const BACKEND_AUTO_SYNC_PLATFORMS = new Set(['temu', 'aliexpress', 'amazon'])
const DEMO_AUTO_SYNC_PLATFORMS = new Set([])

const PLATFORM_LABELS = Object.fromEntries(
  [...MARKETPLACE_PLATFORM_OPTIONS, ...DOMESTIC_PLATFORM_OPTIONS, ...DTC_PLATFORM_OPTIONS].map(
    (item) => [item.value, item.label],
  ),
)

function platformLabel(platform) {
  return PLATFORM_LABELS[platform] || platform
}

function isBackendUnavailable(err) {
  const code = String(err?.errorCode || err?.code || '').trim()
  const message = String(err?.message || '')
  return code === 'SERVER_ERROR'
    || /后端服务未启动|Network Error|ECONNREFUSED|socket hang up/i.test(message)
}

function isSyncConflict(err) {
  const code = String(err?.errorCode || err?.code || '').trim()
  return code === 'CRAWL_IN_PROGRESS' || code === 'AMAZON_SYNC_IN_PROGRESS'
}

function createSyncItem(store) {
  return {
    key: `${store.platform}:${store.id}`,
    platform: store.platform,
    storeId: store.id,
    storeName: store.storeName,
    externalShopId: store.externalShopId || '',
    platformLabel: platformLabel(store.platform),
    status: 'pending',
    message: '',
    syncedAt: '',
    rowCount: 0,
  }
}

export async function buildPlatformSyncTargets(auth) {
  const res = await fetchAllPlatformStores()
  return scopeStores(res.data || [], auth).map(createSyncItem)
}

function markItems(items, predicate, patch) {
  for (const item of items) {
    if (predicate(item)) {
      Object.assign(item, patch)
    }
  }
}

function resolveTemuShopId(target, temuShops = []) {
  return temuShops.find(
    (shop) =>
      shop.accountId === target.storeId
      || shop.id === target.storeId
      || (target.externalShopId && shop.externalShopId === target.externalShopId)
      || (target.externalShopId && shop.id === target.externalShopId)
      || shop.id === target.externalShopId
      || shop.storeName === target.storeName,
  )?.id
}

function applyTemuCrawlSuccess(temuTargets, temuShops, job = {}) {
  const rowsCount = Number(job.rows_count ?? job.rowsCount ?? 0)
  const reportTime = job.report_time || job.reportTime || ''
  if (rowsCount <= 0) return false

  let applied = false
  for (const target of temuTargets) {
    const shopId = resolveTemuShopId(target, temuShops)
    if (!shopId) {
      target.status = 'failed'
      target.message = '店铺尚未关联 Temu Shop ID，请到 Temu 运营页刷新后重试'
      continue
    }
    target.status = 'success'
    target.rowCount = rowsCount
    target.syncedAt = reportTime
    target.message = `已同步 ${rowsCount} 条销售数据`
    applied = true
  }
  return applied
}

async function verifyTemuShopTargets(temuTargets, temuShops, reportTime, job = {}) {
  if (applyTemuCrawlSuccess(temuTargets, temuShops, job)) {
    return
  }

  for (const target of temuTargets) {
    if (target.status === 'success') continue

    const shopId = resolveTemuShopId(target, temuShops)
    if (!shopId) {
      target.status = 'failed'
      target.message = '店铺尚未关联 Temu Shop ID，请到 Temu 运营页刷新后重试'
      continue
    }

    try {
      const data = await fetchTemuOperationalData({ shopId })
      const count = data.products?.length ?? 0
      target.rowCount = count
      target.syncedAt = data.meta?.reportTime || reportTime || ''
      if (count > 0) {
        target.status = 'success'
        target.message = `已同步 ${count} 条 SKU`
      } else {
        target.status = 'empty'
        target.message = '爬取完成，但未读取到当日销量数据'
      }
    } catch (err) {
      target.status = 'failed'
      target.message = err.message || '读取店铺数据失败'
    }
  }
}

function applyPlatformJobStatus(targets, platformStatus, schedule, platformLabel) {
  const lastJob = platformStatus?.last_job
  const scheduleHint = schedule?.time_label
    ? `全平台 ${schedule.time_label}${schedule.next_run_hint ? ` · 下次约 ${schedule.next_run_hint}` : ''}`
    : '全平台每天 09:30'

  if (!lastJob) {
    for (const target of targets) {
      target.status = 'skipped'
      target.message = `${platformLabel}按日批同步（${scheduleHint}），尚无同步记录`
    }
    return
  }

  const status = String(lastJob.status || '').toLowerCase()
  const finishedAt = lastJob.finished_at || lastJob.created_at || ''
  const trigger = lastJob.trigger === 'daily_schedule' ? '日批' : '手动'
  if (status === 'success' || status === 'partial') {
    for (const target of targets) {
      if (target.status === 'failed' || target.status === 'empty') continue
      target.status = status === 'partial' ? 'partial' : 'success'
      target.message = [
        `${trigger}同步成功`,
        finishedAt ? `于 ${finishedAt}` : '',
        scheduleHint,
      ].filter(Boolean).join(' · ')
      target.syncedAt = finishedAt || target.syncedAt
      if (lastJob.rows_count != null) target.rowCount = lastJob.rows_count
    }
    return
  }
  if (status === 'pending' || status === 'running') {
    for (const target of targets) {
      target.status = 'syncing'
      target.message = `${trigger}同步进行中…`
    }
    return
  }
  if (status === 'failed') {
    const errMsg = formatCrawlError(lastJob.error_code, lastJob.error_message || platformStatus.error_message)
    for (const target of targets) {
      target.status = 'failed'
      target.message = errMsg || `${platformLabel}日批同步失败`
    }
  }
}

function applyTemuDailySyncStatus(temuTargets, syncStatus) {
  const schedule = syncStatus?.schedule || {}
  const temuStatus = syncStatus?.platforms?.temu || syncStatus
  const reportHint = (temuStatus?.data_report_time || syncStatus?.data_report_time)
    ? `数据日 ${temuStatus?.data_report_time || syncStatus?.data_report_time}`
    : ''
  applyPlatformJobStatus(temuTargets, temuStatus, schedule, 'Temu ')
  if (reportHint) {
    for (const target of temuTargets) {
      if (target.status === 'success' || target.status === 'partial') {
        target.message = `${target.message} · ${reportHint}`
      }
    }
  }
}

async function syncTemuStores(auth, items, onProgress, crawlOpts = {}) {
  const temuTargets = items.filter((item) => item.platform === 'temu')
  if (!temuTargets.length) return

  if (!canUseTemuBackend(auth)) {
    markItems(items, (item) => item.platform === 'temu', {
      status: 'skipped',
      message: '未启用后端模式，无法自动爬取',
    })
    onProgress?.([...items])
    return
  }

  // 默认走全平台日批（每天 09:30）；登录打开应用只展示状态，不强制再爬。
  // 「重新同步」带 force=true 仍立即爬取。
  if (!crawlOpts.force) {
    try {
      const syncStatus = await fetchTemuSyncStatus()
      const temuShops = await fetchTemuStores(auth).catch(() => [])
      const temuStatus = syncStatus?.platforms?.temu || syncStatus
      await verifyTemuShopTargets(
        temuTargets,
        temuShops,
        temuStatus?.data_report_time || syncStatus?.data_report_time || '',
        temuStatus?.last_job || {},
      )
      applyTemuDailySyncStatus(temuTargets, syncStatus)
    } catch (err) {
      markItems(items, (item) => item.platform === 'temu', {
        status: 'skipped',
        message: err.message || '无法读取 Temu 同步状态',
      })
    }
    onProgress?.([...items])
    return
  }

  markItems(items, (item) => item.platform === 'temu', {
    status: 'syncing',
    message: '正在检查 Temu 登录状态...',
  })
  onProgress?.([...items])

  try {
    let session = await fetchTemuSessionStatus()
    if (!session.ready) {
      if (!session.profile_busy) {
        try {
          await openTemuSellerLogin()
        } catch {
          // best effort
        }
      }
      markItems(items, (item) => item.platform === 'temu', {
        status: 'syncing',
        message: '等待 Temu 卖家后台登录...',
      })
      onProgress?.([...items])
      try {
        session = await pollTemuSessionUntilReady({
          timeoutMs: 300000,
          intervalMs: 2000,
          maxIntervalMs: 5000,
          maxAttempts: 72,
        })
      } catch {
        markItems(items, (item) => item.platform === 'temu', {
          status: 'skipped',
          message: '尚未完成 Temu 登录，请到 Temu 运营页刷新数据',
        })
        onProgress?.([...items])
        return
      }
    }

    try {
      await pollTemuProfileIdle({
        timeoutMs: 120000,
        intervalMs: 2000,
        maxIntervalMs: 5000,
        maxAttempts: 36,
      })
    } catch {
      markItems(items, (item) => item.platform === 'temu', {
        status: 'skipped',
        message: '登录窗口仍占用浏览器，请关闭后重试',
      })
      onProgress?.([...items])
      return
    }

    markItems(items, (item) => item.platform === 'temu', {
      status: 'syncing',
      message: '正在同步 Temu 销售数据...',
    })
    onProgress?.([...items])

    const result = await refreshTemuDataWithCrawl(crawlOpts)
    const reportTime = result.job?.report_time || ''
    const temuShops = await fetchTemuStores(auth)
    await verifyTemuShopTargets(temuTargets, temuShops, reportTime, result.job || {})
    if (result.partial) {
      for (const target of temuTargets) {
        if (target.status === 'success' && result.message) {
          target.message = result.message
        }
      }
    }

    if (auth.isBoss) {
      try {
        const competitorSync = await autoSyncCompetitorTargetsOnPlatformRefresh({
          maxTargets: 3,
          ...crawlOpts,
        })
        if (competitorSync.triggered > 0) {
          for (const target of temuTargets) {
            if (target.status === 'success' || target.status === 'partial') {
              target.message = `${target.message}；已排队 ${competitorSync.triggered} 个竞品快照`
            }
          }
        }
      } catch {
        // 竞品自动同步失败不影响 Temu 销售同步结果
      }
    }
  } catch (err) {
    if (isBackendUnavailable(err)) {
      markItems(items, (item) => item.platform === 'temu', {
        status: 'skipped',
        message: '后端暂不可用，已跳过 Temu 自动同步',
      })
    } else {
      const temuShops = await fetchTemuStores(auth).catch(() => [])
      await verifyTemuShopTargets(temuTargets, temuShops, '', {})
      markItems(
        items,
        (item) => item.platform === 'temu' && item.status === 'syncing',
        {
          status: 'failed',
          message: err.message || 'Temu 自动同步失败',
        },
      )
    }
  }

  onProgress?.([...items])
}

async function syncAliExpressStores(auth, items, onProgress, crawlOpts = {}) {
  const targets = items.filter((item) => item.platform === 'aliexpress')
  if (!targets.length) return

  if (!canUseAliExpressBackend(auth)) {
    markItems(items, (item) => item.platform === 'aliexpress', {
      status: 'skipped',
      message: '未启用后端模式，无法自动爬取',
    })
    onProgress?.([...items])
    return
  }

  if (!crawlOpts.force) {
    try {
      const syncStatus = await fetchTemuSyncStatus()
      applyPlatformJobStatus(targets, syncStatus?.platforms?.aliexpress, syncStatus?.schedule, '速卖通')
      try {
        const [orderRes, violationRes] = await Promise.all([
          fetchTodayAliExpressOrdersFromApi(),
          loadAliExpressViolationsFromApi(),
        ])
        const syncedAt = orderRes.syncedAt || violationRes.syncedAt || ''
        for (const target of targets) {
          if (target.status === 'failed' || target.status === 'syncing') continue
          const orderCount = (orderRes.orders || []).filter((order) => order.storeId === target.storeId).length
          const violationCount = (violationRes.violations || []).filter((item) => item.storeId === target.storeId).length
          if (orderCount > 0 || violationCount > 0) {
            target.status = 'success'
            target.rowCount = orderCount + violationCount
            target.syncedAt = syncedAt || target.syncedAt
            target.message = `已入库 ${orderCount} 笔订单、${violationCount} 条违规 · 全平台每天 09:30`
          }
        }
      } catch {
        // keep schedule status
      }
    } catch (err) {
      markItems(items, (item) => item.platform === 'aliexpress', {
        status: 'skipped',
        message: err.message || '无法读取速卖通同步状态',
      })
    }
    onProgress?.([...items])
    return
  }

  markItems(items, (item) => item.platform === 'aliexpress', {
    status: 'syncing',
    message: '无头浏览器爬取订单与违规...',
  })
  onProgress?.([...items])

  function applyAliExpressTargets({ crawlRes, orders, violations, syncedAt }) {
    for (const target of targets) {
      const orderCount = orders.filter((order) => order.storeId === target.storeId).length
      const violationCount = violations.filter((item) => item.storeId === target.storeId).length
      target.syncedAt = syncedAt
      target.rowCount = orderCount + violationCount
      const orderPart = `${orderCount} 笔今日订单`
      const violationPart = `${violationCount} 条违规`
      if (orderCount > 0 || violationCount > 0) {
        target.status = crawlRes?.partial ? 'partial' : 'success'
        target.message = crawlRes?.partial
          ? `已同步 ${orderPart}、${violationPart}（任务部分成功）`
          : `已同步 ${orderPart}、${violationPart}`
      } else {
        target.status = crawlRes?.partial ? 'partial' : 'empty'
        target.message = crawlRes?.partial
          ? '爬取部分成功，但今日暂无订单与违规记录'
          : '店铺已绑定，但今日暂无订单与违规记录'
      }
    }
  }

  try {
    const crawlRes = await refreshAliExpressDataWithCrawl({ scope: 'all', ...crawlOpts })
    const [orderRes, violationRes] = await Promise.all([
      fetchTodayAliExpressOrdersFromApi(),
      loadAliExpressViolationsFromApi(),
    ])
    applyAliExpressTargets({
      crawlRes,
      orders: orderRes.orders || [],
      violations: violationRes.violations || [],
      syncedAt: orderRes.syncedAt || violationRes.syncedAt || '',
    })
  } catch (err) {
    if (isBackendUnavailable(err)) {
      markItems(items, (item) => item.platform === 'aliexpress', {
        status: 'skipped',
        message: '后端暂不可用，已跳过 AliExpress 自动同步',
      })
    } else {
      try {
        const [orderRes, violationRes] = await Promise.all([
          fetchTodayAliExpressOrdersFromApi(),
          loadAliExpressViolationsFromApi(),
        ])
        applyAliExpressTargets({
          crawlRes: { partial: true },
          orders: orderRes.orders || [],
          violations: violationRes.violations || [],
          syncedAt: orderRes.syncedAt || violationRes.syncedAt || '',
        })
        for (const target of targets) {
          if (target.status === 'success' || target.status === 'partial') {
            target.message = `${target.message}（爬取任务异常但数据已入库）`
          } else if (target.status === 'syncing') {
            target.status = isSyncConflict(err) ? 'skipped' : 'failed'
            target.message = isSyncConflict(err)
              ? (err.message || '已有爬取任务进行中，请稍后在页面手动同步')
              : (err.message || 'AliExpress 同步失败')
          }
        }
      } catch {
        markItems(items, (item) => item.platform === 'aliexpress', {
          status: isSyncConflict(err) ? 'skipped' : 'failed',
          message: err.message || 'AliExpress 同步失败',
        })
      }
    }
  }

  onProgress?.([...items])
}

async function syncAmazonStores(auth, items, onProgress, crawlOpts = {}) {
  const targets = items.filter((item) => item.platform === 'amazon')
  if (!targets.length) return

  if (!canUseAmazonBackend()) {
    markItems(items, (item) => item.platform === 'amazon', {
      status: 'skipped',
      message: '未启用后端模式，无法自动同步',
    })
    onProgress?.([...items])
    return
  }

  if (!crawlOpts.force) {
    try {
      const syncStatus = await fetchTemuSyncStatus()
      applyPlatformJobStatus(targets, syncStatus?.platforms?.amazon, syncStatus?.schedule, 'Amazon ')
    } catch (err) {
      markItems(items, (item) => item.platform === 'amazon', {
        status: 'skipped',
        message: err.message || '无法读取 Amazon 同步状态',
      })
    }
    onProgress?.([...items])
    return
  }

  let integration = {}
  let ziniaoReady = false
  let agentReady = false
  let localAgentProcess = false
  try {
    const [statusRes, localZiniao, localAgent] = await Promise.all([
      fetchAmazonIntegrationStatus(),
      probeLocalZiniao(),
      probeLocalAgent(),
    ])
    integration = statusRes.data || {}
    ziniaoReady = localZiniao || Boolean(integration.ziniao_online)
    localAgentProcess = Boolean(localAgent)
    // P0：只认当前企业心跳，禁止本机 :18765 冒充在线
    agentReady = Boolean(integration.agent_online)
  } catch {
    integration = {}
  }

  if (!agentReady) {
    const mismatch = localAgentProcess && !Boolean(integration.agent_online)
    markItems(items, (item) => item.platform === 'amazon', {
      status: 'failed',
      message: mismatch
        ? '本机有同步进程，但当前企业未收到心跳（config.json 可能绑错企业）。请联系运维用正确 agent_token 重启 CrossHub-Sync-Helper.exe'
        : '本机同步程序未在线，请联系运维启动 CrossHub-Sync-Helper.exe',
    })
    onProgress?.([...items])
    return
  }

  if (!ziniaoReady) {
    markItems(items, (item) => item.platform === 'amazon', {
      status: 'failed',
      message: '紫鸟 WebDriver 未就绪，请联系运维确认 CrossHub-Sync-Helper.exe 已启动紫鸟',
    })
    onProgress?.([...items])
    return
  }

  markItems(items, (item) => item.platform === 'amazon', {
    status: 'syncing',
    message: '紫鸟 Agent 同步账户状况...',
  })
  onProgress?.([...items])

  try {
    const stores = scopeStores((await fetchAmazonStores()).data || [], auth)
    const started = await refreshAmazonAccountHealth(stores, { refresh: true, ...crawlOpts })
    const daily = started.data || (await fetchAmazonDailyFromBackend(stores)).data
    let insights = { products: [] }
    try {
      insights = (await fetchAmazonInsightsFromBackend(stores)).data || { products: [] }
    } catch {
      insights = { products: [] }
    }
    const syncedAt = daily.syncedAt || insights.syncedAt || ''
    for (const target of targets) {
      const metrics = (daily.accountMetrics || []).filter((m) => m.storeId === target.storeId)
      const reviews = (daily.reviews || []).filter((r) => r.storeId === target.storeId)
      const coupons = (daily.coupons || []).filter((c) => c.storeId === target.storeId)
      const shipments = (daily.shipments || []).filter((s) => s.storeId === target.storeId)
      const products = (insights.products || []).filter((p) => p.storeId === target.storeId)
      const rowCount = metrics.length + reviews.length + coupons.length + shipments.length + products.length
      target.syncedAt = syncedAt
      target.rowCount = rowCount
      if (rowCount > 0) {
        target.status = 'success'
        const parts = []
        if (products.length) parts.push(`${products.length} SKU`)
        if (metrics.length) parts.push(`${metrics.length} 指标`)
        if (reviews.length) parts.push(`${reviews.length} 差评`)
        if (coupons.length) parts.push(`${coupons.length} 优惠券`)
        if (shipments.length) parts.push(`${shipments.length} 货件`)
        target.message = parts.length ? `已同步 ${parts.join(' / ')}` : '已同步 Amazon 数据'
      } else if (started.partial) {
        target.status = 'empty'
        target.message = started.warning || '账户状况同步完成，暂无运营待办数据'
      } else {
        target.status = 'empty'
        target.message = started.message || '同步完成，暂无运营待办数据'
      }
    }
  } catch (err) {
    if (isBackendUnavailable(err)) {
      markItems(items, (item) => item.platform === 'amazon', {
        status: 'skipped',
        message: '后端暂不可用，已跳过 Amazon 自动同步',
      })
    } else if (isSyncConflict(err)) {
      markItems(items, (item) => item.platform === 'amazon', {
        status: 'skipped',
        message: err.message || '已有 Amazon 同步任务进行中，请在运营页手动刷新',
      })
    } else {
      markItems(items, (item) => item.platform === 'amazon', {
        status: 'failed',
        message: err.message || 'Amazon 自动同步失败',
      })
    }
  }

  onProgress?.([...items])
}

function shouldHydrateStatus(status) {
  return status === 'pending' || status === 'syncing' || status === 'skipped'
}

function applyAmazonTargetsFromCache(targets, stores, daily, insights) {
  const syncedAt = daily.syncedAt || insights.syncedAt || ''
  for (const target of targets) {
    const metrics = (daily.accountMetrics || []).filter((m) => m.storeId === target.storeId)
    const reviews = (daily.reviews || []).filter((r) => r.storeId === target.storeId)
    const coupons = (daily.coupons || []).filter((c) => c.storeId === target.storeId)
    const shipments = (daily.shipments || []).filter((s) => s.storeId === target.storeId)
    const products = (insights.products || []).filter((p) => p.storeId === target.storeId)
    const rowCount = metrics.length + reviews.length + coupons.length + shipments.length + products.length
    target.syncedAt = syncedAt
    target.rowCount = rowCount
    if (rowCount > 0) {
      target.status = 'success'
      const parts = []
      if (products.length) parts.push(`${products.length} SKU`)
      if (metrics.length) parts.push(`${metrics.length} 指标`)
      if (reviews.length) parts.push(`${reviews.length} 差评`)
      if (coupons.length) parts.push(`${coupons.length} 优惠券`)
      if (shipments.length) parts.push(`${shipments.length} 货件`)
      target.message = parts.length ? `已同步 ${parts.join(' / ')}` : '已同步 Amazon 数据'
    } else {
      target.status = 'empty'
      target.message = '暂无 Amazon 入库数据'
    }
  }
}

/** 用后端已入库数据回填仍为 pending/syncing 的侧栏项，避免与各运营页实际数据不一致 */
export async function hydratePlatformSyncFromBackend(auth, items) {
  if (!auth?.backendLinked || auth.isWarehouse || !items?.length) return

  const temuTargets = items.filter((item) => item.platform === 'temu' && shouldHydrateStatus(item.status))
  if (temuTargets.length && canUseTemuBackend(auth)) {
    const temuShops = await fetchTemuStores(auth).catch(() => [])
    await verifyTemuShopTargets(temuTargets, temuShops, '', {})
  }

  const aliexpressTargets = items.filter(
    (item) => item.platform === 'aliexpress' && shouldHydrateStatus(item.status),
  )
  if (aliexpressTargets.length && canUseAliExpressBackend(auth)) {
    try {
      const [orderRes, violationRes, operationalRes] = await Promise.all([
        fetchTodayAliExpressOrdersFromApi(),
        loadAliExpressViolationsFromApi(),
        fetchAliExpressOperationalData().catch(() => ({ products: [] })),
      ])
      const productCountByStore = {}
      for (const product of operationalRes.products || []) {
        const storeId = product.storeId || product.store_id
        if (!storeId) continue
        productCountByStore[storeId] = (productCountByStore[storeId] || 0) + 1
      }
      const targets = aliexpressTargets
      const applyCache = (orders, violations, syncedAt) => {
        for (const target of targets) {
          const orderCount = orders.filter((order) => order.storeId === target.storeId).length
          const violationCount = violations.filter((item) => item.storeId === target.storeId).length
          const productCount = productCountByStore[target.storeId] || 0
          const rowCount = orderCount + violationCount + productCount
          target.syncedAt = syncedAt
          target.rowCount = rowCount
          if (rowCount > 0) {
            target.status = 'success'
            const parts = []
            if (orderCount > 0) parts.push(`${orderCount} 笔今日订单`)
            if (violationCount > 0) parts.push(`${violationCount} 条违规`)
            if (productCount > 0) parts.push(`${productCount} 个商品`)
            target.message = `已同步 ${parts.join('、')}`
          } else {
            target.status = 'empty'
            target.message = '店铺已绑定，但暂无入库数据'
          }
        }
      }
      applyCache(
        orderRes.orders || [],
        violationRes.violations || [],
        orderRes.syncedAt || violationRes.syncedAt || '',
      )
    } catch {
      // best effort
    }
  }

  const amazonTargets = items.filter(
    (item) => item.platform === 'amazon' && shouldHydrateStatus(item.status),
  )
  if (amazonTargets.length && canUseAmazonBackend()) {
    try {
      const stores = scopeStores((await fetchAmazonStores()).data || [], auth)
      const [dailyRes, insightsRes] = await Promise.all([
        fetchAmazonDailyFromBackend(stores),
        fetchAmazonInsightsFromBackend(stores).catch(() => ({ data: { products: [] } })),
      ])
      applyAmazonTargetsFromCache(amazonTargets, stores, dailyRes.data || {}, insightsRes.data || {})
    } catch {
      // best effort
    }
  }
}

export async function runPlatformAutoSync(auth, { onProgress, force = false } = {}) {
  if (!force && isPlatformCrawlInCooldown(auth)) {
    const items = await buildPlatformSyncTargets(auth)
    await hydratePlatformSyncFromBackend(auth, items)
    onProgress?.([...items])
    return {
      items,
      skipped: true,
      cooldown: true,
      reason: 'cooldown',
      message: `同步冷却中，${formatCooldownRemaining(getCooldownRemainingMs(auth))}后可再次全量同步`,
    }
  }

  const items = await buildPlatformSyncTargets(auth)
  if (!items.length) {
    return { items: [], skipped: true, reason: 'no_stores' }
  }

  markItems(
    items,
    (item) => !BACKEND_AUTO_SYNC_PLATFORMS.has(item.platform) && !DEMO_AUTO_SYNC_PLATFORMS.has(item.platform),
    {
      status: 'skipped',
      message: '该平台暂未接入自动同步',
    },
  )
  onProgress?.([...items])

  const crawlOpts = createPlatformSyncBatchOptions(force)

  const hasTemuTargets = items.some((item) => item.platform === 'temu')
  if (hasTemuTargets) {
    await syncTemuStores(auth, items, onProgress, crawlOpts)
  }

  const hasAliExpressTargets = items.some((item) => item.platform === 'aliexpress')
  if (hasAliExpressTargets) {
    await syncAliExpressStores(auth, items, onProgress, crawlOpts)
  }

  const hasAmazonTargets = items.some((item) => item.platform === 'amazon')
  if (hasAmazonTargets) {
    await syncAmazonStores(auth, items, onProgress, crawlOpts)
  }

  await hydratePlatformSyncFromBackend(auth, items)
  onProgress?.([...items])

  markPlatformCrawlOnSuccess(auth, items)
  if (hasSuccessfulSyncItems(items)) {
    await touchPlatformCrawlCooldown().catch(() => {})
  }

  return { items, skipped: false }
}
