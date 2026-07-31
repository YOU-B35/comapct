import { service } from './request'
import { mapMonitorReport } from '@/utils/temuMonitorReport'
import {
  markPlatformCrawlOnSuccess,
  normalizeCrawlOptions,
  throwIfCrawlCooldownResponse,
} from '@/utils/platformSyncCooldown'
import { AppApiError, getAppErrorMessage } from '@/utils/appErrorCode'
import { isTemuMallUrl, temuMallUrlErrorMessage } from '@/utils/temuMonitorUrl'

function unwrap(res) {
  return res?.data ?? res
}

function isActiveStatus(status) {
  return status === 'pending' || status === 'running'
}

function isTerminalStatus(status) {
  return status === 'success' || status === 'failed'
}

function parseHost(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url || ''
  }
}

function mapTarget(item) {
  return {
    id: item.id,
    label: item.label,
    url: item.target_url,
    host: item.host || parseHost(item.target_url),
    status: item.status,
    freshnessMinutes: item.freshness_minutes,
    latestSnapshotId: item.latest_snapshot_id || null,
    latestSnapshotAt: item.latest_snapshot_at || null,
    lastAnalyzedAt: item.latest_snapshot_at || null,
  }
}

async function fetchMonitorLatest(id) {
  const res = await service.get(`/api/monitor/targets/${id}/latest`)
  return unwrap(res) || {}
}

async function fetchMonitorHistory(id) {
  const res = await service.get(`/api/monitor/targets/${id}/history`)
  return unwrap(res) || { snapshots: [], jobs: [] }
}

async function fetchMonitorJob(jobId) {
  const res = await service.get(`/api/monitor/jobs/${jobId}`)
  return unwrap(res) || {}
}

async function triggerMonitorTarget(id, options = {}) {
  const normalized = typeof options === 'string' ? { reason: options } : options
  // Monitor cooldown is server-side monitor:{id} only — do not gate on FE platform 3h localStorage.
  const crawlOpts = normalizeCrawlOptions(normalized)

  const res = await service.post(`/api/monitor/targets/${id}/trigger`, {
    reason: normalized.reason || 'manual refresh',
    force: !!crawlOpts.force,
    // 显式 force 或 bypassCooldown 均可绕过租户级冷却（「执行今日爬取分析」会传 force）
    bypass_cooldown: Boolean(normalized.bypassCooldown || crawlOpts.force),
  }, { skipGlobalErrorToast: true, validateStatus: () => true })

  const payload = res?.data ?? res
  throwIfCrawlCooldownResponse(res, payload, '竞品监控爬取冷却中')
  if (res.status >= 400) {
    throw new AppApiError(
      getAppErrorMessage(payload?.error_code, payload?.msg || '触发竞品监控失败'),
      payload?.error_code || 'MONITOR_JOB_FAILED',
    )
  }
  return payload?.data ?? payload ?? {}
}

async function downloadMonitorTargetReportXlsx(id) {
  return service.get(`/api/monitor/targets/${id}/report.xlsx`, {
    responseType: 'blob',
  })
}

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

async function waitForJob(jobId, maxAttempts = 6, delayMs = 1000) {
  let lastJob = null
  for (let i = 0; i < maxAttempts; i += 1) {
    lastJob = await fetchMonitorJob(jobId)
    if (isTerminalStatus(lastJob.status)) {
      return lastJob
    }
    await wait(delayMs)
  }
  return lastJob
}

async function waitForActiveJob(targetId, latest = {}, maxAttempts = 6, delayMs = 1000) {
  if (!isActiveStatus(latest.latest_job_status || latest.latestJobStatus)) {
    return null
  }
  const history = await fetchMonitorHistory(targetId)
  const activeJobId = history.jobs?.[0]?.jobId || history.jobs?.[0]?.job_id
  if (!activeJobId) {
    return null
  }
  return waitForJob(activeJobId, maxAttempts, delayMs)
}

const MANUAL_CRAWL_POLL_ATTEMPTS = 30
const MANUAL_CRAWL_POLL_DELAY_MS = 2000

async function enqueueManualCrawl(target, options = {}) {
  const crawlOpts = normalizeCrawlOptions(options)
  const latest = await fetchMonitorLatest(target.id)
  const latestJobStatus = latest.latest_job_status || latest.latestJobStatus

  if (isActiveStatus(latestJobStatus)) {
    await waitForActiveJob(
      target.id,
      latest,
      MANUAL_CRAWL_POLL_ATTEMPTS,
      MANUAL_CRAWL_POLL_DELAY_MS,
    )
    return
  }

  try {
    const job = await triggerMonitorTarget(target.id, {
      reason: 'manual refresh',
      ...options,
    })
    const jobId = job?.job_id || job?.jobId
    if (jobId) {
      const finished = await waitForJob(jobId, MANUAL_CRAWL_POLL_ATTEMPTS, MANUAL_CRAWL_POLL_DELAY_MS)
      if (finished?.status === 'success') {
        markPlatformCrawlOnSuccess(null, { success: true }, { enabled: crawlOpts.recordCooldown })
      }
    }
  } catch (error) {
    if (error?.errorCode === 'MONITOR_JOB_IN_PROGRESS' && error?.data?.job_id) {
      await waitForJob(
        error.data.job_id,
        MANUAL_CRAWL_POLL_ATTEMPTS,
        MANUAL_CRAWL_POLL_DELAY_MS,
      )
      return
    }
    if (error?.errorCode === 'CRAWL_COOLDOWN') {
      throw error
    }
    if (error?.errorCode !== 'MONITOR_JOB_IN_PROGRESS') {
      throw error
    }
  }
}

/** 顶栏 Temu 同步后：对无当日快照的 monitor 竞品目标排队抓取 */
export async function autoSyncCompetitorTargetsOnPlatformRefresh(options = {}) {
  const maxTargets = Number(options.maxTargets || 3)
  const competitorsRes = await fetchBackendCompetitors()
  const targets = (competitorsRes.data || []).filter((item) => item.status === 'active')
  let triggered = 0
  let skipped = 0

  for (const target of targets) {
    if (triggered >= maxTargets) break
    try {
      const latest = await fetchMonitorLatest(target.id)
      if (latest.has_fresh_data) {
        skipped += 1
        continue
      }
      if (!latest.can_trigger_now) {
        skipped += 1
        continue
      }
      await triggerMonitorTarget(target.id, {
        reason: 'platform sync auto',
        force: false,
        ...options,
      })
      triggered += 1
    } catch (error) {
      if (error?.errorCode === 'MONITOR_JOB_IN_PROGRESS' || error?.errorCode === 'CRAWL_COOLDOWN') {
        skipped += 1
        continue
      }
      throw error
    }
  }

  return { triggered, skipped, total: targets.length }
}

async function buildReportForTarget(target) {
  const [latest, history] = await Promise.all([
    fetchMonitorLatest(target.id),
    fetchMonitorHistory(target.id),
  ])
  return mapMonitorReport(target, latest, history)
}

export async function fetchBackendCompetitors() {
  const res = await service.get('/api/monitor/targets', {
    params: { platform: 'temu' },
  })
  return { success: true, data: (unwrap(res) || []).map(mapTarget) }
}

export async function saveBackendCompetitor(payload) {
  const url = String(payload?.url || '').trim()
  if (!isTemuMallUrl(url)) {
    throw new AppApiError(temuMallUrlErrorMessage, 'MONITOR_TARGET_URL_INVALID')
  }
  const body = {
    platform: 'temu',
    target_type: 'shop',
    label: payload.label,
    target_url: url,
    freshness_minutes: 1440,
    crawl_strategy: 'store_listing',
    status: 'active',
  }
  const res = payload.id
    ? await service.put(`/api/monitor/targets/${payload.id}`, body)
    : await service.post('/api/monitor/targets', body)
  return { success: true, data: mapTarget(unwrap(res)) }
}

export async function deleteBackendCompetitor(id) {
  const res = await service.delete(`/api/monitor/targets/${id}`)
  return { success: true, data: unwrap(res) }
}

export async function fetchBackendCompetitorReports() {
  const competitorsRes = await fetchBackendCompetitors()
  const competitors = competitorsRes.data || []
  const reports = await Promise.all(competitors.map((item) => buildReportForTarget(item)))
  return { success: true, data: reports, competitors }
}

export async function discoverBackendCompetitors(payload = {}) {
  const res = await service.post('/api/temu/competitors/discover', {
    keyword: payload.keyword || 'fishing tackle',
    region: payload.region || 'za',
    limit: payload.limit || 10,
    // Manual discovery is operator-driven; force bypass crawl cooldown for testing/ops.
    force: true,
  }, { skipGlobalErrorToast: true, validateStatus: () => true })
  const body = res?.data ?? res
  throwIfCrawlCooldownResponse(res, body, '竞店发现冷却中')
  if (res.status >= 400) {
    const rawMsg = body?.msg || body?.message || '竞店发现失败'
    let errorCode = body?.error_code || ''
    if (!errorCode || errorCode === 'UNKNOWN') {
      const matched = String(rawMsg).match(/^(COMPETITOR_[A-Z0-9_]+)/)
      if (matched) errorCode = matched[1]
    }
    if (errorCode === 'COMPETITOR_FRONTEND_LOGIN_REQUIRED') {
      errorCode = 'COMPETITOR_LOGIN_REQUIRED'
    }
    throw new AppApiError(
      getAppErrorMessage(errorCode, rawMsg),
      errorCode || 'COMPETITOR_DISCOVERY_NO_RESULTS',
    )
  }
  return { success: true, data: unwrap(res) || {} }
}

export async function analyzeBackendCompetitors(competitors = [], options = {}) {
  const selectedIds = new Set((competitors || []).map((item) => item.id).filter(Boolean))
  const competitorsRes = await fetchBackendCompetitors()
  const allCompetitors = competitorsRes.data || []
  const targets = selectedIds.size
    ? allCompetitors.filter((item) => selectedIds.has(item.id))
    : allCompetitors

  const validTargets = targets.filter((item) => isTemuMallUrl(item.url))
  if (!validTargets.length) {
    throw new AppApiError(temuMallUrlErrorMessage, 'MONITOR_TARGET_URL_INVALID')
  }

  // 默认不强制；冷却时由 UI 二次确认后再传 force / bypassCooldown
  const crawlOptions = {
    force: false,
    bypassCooldown: false,
    recordCooldown: false,
    ...options,
  }

  for (const target of validTargets) {
    await enqueueManualCrawl(target, crawlOptions)
  }

  const reports = await Promise.all(validTargets.map((item) => buildReportForTarget(item)))
  return {
    success: true,
    data: reports,
    competitors: allCompetitors,
    skippedInvalidUrlCount: targets.length - validTargets.length,
  }
}

export async function downloadBackendCompetitorReport(report) {
  const blob = await downloadMonitorTargetReportXlsx(report.id)
  const objectUrl = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = `${report.label || 'monitor-report'}-${report.crawlDate || 'latest'}.xlsx`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.URL.revokeObjectURL(objectUrl)
}
