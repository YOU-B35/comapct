import axios from 'axios'
import { AppApiError, toAppApiError } from '@/utils/appErrorCode'
import { service, getAccessToken } from './request'
import { TEMU_API_BASE_URL } from './config'

const JOB_POLL_MS = 2500
const JOB_MAX_WAIT_MS = 300000

const TERMINAL_STATUSES = new Set(['success', 'partial', 'failed', 'cancelled', 'canceled'])

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function unwrapData(res) {
  return res?.data ?? res ?? {}
}

/** 助手任务状态 → 中文提示 */
export function formatTemuJobStatusZh(status) {
  const key = String(status || '').toLowerCase()
  switch (key) {
    case 'pending':
      return '排队中'
    case 'running':
      return '同步进行中'
    case 'retry_wait':
      return '等待重试'
    case 'success':
      return '同步成功'
    case 'partial':
      return '部分完成'
    case 'failed':
      return '同步失败'
    case 'cancelled':
    case 'canceled':
      return '已取消'
    default:
      return status ? `状态：${status}` : '处理中'
  }
}

export function isTemuJobTerminal(status) {
  return TERMINAL_STATUSES.has(String(status || '').toLowerCase())
}

/** GET /api/agent/me/status */
export async function fetchMyAgentStatus() {
  const res = await service.get('/api/agent/me/status', { skipGlobalErrorToast: true })
  return unwrapData(res)
}

/** POST /api/agent/me/bind-code → { code, expires_at, expires_in_seconds } */
export async function createBindCode() {
  const res = await service.post('/api/agent/me/bind-code', {}, { skipGlobalErrorToast: true })
  return unwrapData(res)
}

/**
 * POST /api/temu/sync/enqueue
 * Uses raw axios for 202 Accepted (same pattern as triggerTemuCrawl).
 */
export async function enqueueTemuSync({ force = false, seed = false, recordCooldown } = {}) {
  const body = {}
  if (force) body.force = true
  if (seed) body.seed = true
  if (recordCooldown != null) body.record_cooldown = Boolean(recordCooldown)

  const token = getAccessToken()
  const res = await axios.post('/api/temu/sync/enqueue', body, {
    baseURL: import.meta.env.DEV ? '' : TEMU_API_BASE_URL,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    validateStatus: () => true,
    timeout: 60000,
    skipGlobalErrorToast: true,
  })

  const payload = res.data
  const data = payload?.data ?? payload
  if (res.status === 202 || payload?.code === 0 || payload?.success) {
    return data
  }
  throw toAppApiError(payload, '提交同步任务失败')
}

/** POST /api/temu/login/enqueue */
export async function enqueueTemuLogin(payload = {}) {
  const body = {}
  if (payload.platformAccountId) {
    body.platform_account_id = payload.platformAccountId
  }
  const res = await service.post('/api/temu/login/enqueue', body, { skipGlobalErrorToast: true })
  return unwrapData(res)
}

/** GET /api/temu/jobs/{id} */
export async function fetchTemuJob(jobId) {
  const res = await service.get(`/api/temu/jobs/${encodeURIComponent(jobId)}`, {
    skipGlobalErrorToast: true,
  })
  return unwrapData(res)
}

/**
 * Enqueue sync then poll every ~2.5s until terminal status.
 * @param {{ force?: boolean, onStatus?: (info: { status: string, label: string, job: object }) => void, signal?: AbortSignal }} options
 */
export async function enqueueAndPollTemuSync(options = {}) {
  const { onStatus, signal, ...enqueueOpts } = options
  const started = await enqueueTemuSync(enqueueOpts)
  const jobId = started.job_id || started.jobId || started.id
  if (!jobId) {
    throw new AppApiError('未获取到同步任务 ID', 'CRAWL_PROCESS_FAILED')
  }

  const deadline = Date.now() + JOB_MAX_WAIT_MS
  let job = started
  onStatus?.({
    status: job.status || 'pending',
    label: formatTemuJobStatusZh(job.status || 'pending'),
    job,
  })

  while (Date.now() < deadline) {
    if (signal?.aborted) {
      throw new AppApiError('已取消同步等待', 'CRAWL_INTERRUPTED')
    }
    if (isTemuJobTerminal(job.status)) break
    await sleep(JOB_POLL_MS)
    if (signal?.aborted) {
      throw new AppApiError('已取消同步等待', 'CRAWL_INTERRUPTED')
    }
    job = await fetchTemuJob(jobId)
    onStatus?.({
      status: job.status,
      label: formatTemuJobStatusZh(job.status),
      job,
    })
  }

  if (!isTemuJobTerminal(job.status)) {
    throw new AppApiError('数据同步超时，请检查本机 Sync Helper 后重试', 'CRAWL_TIMEOUT')
  }

  if (job.status === 'failed') {
    throw new AppApiError(
      job.msg || job.error_message || '数据同步失败',
      job.error_code || 'CRAWL_PROCESS_FAILED',
    )
  }

  return {
    success: true,
    partial: job.status === 'partial',
    job,
    jobId,
  }
}

/** 线上静态占位路径；真实 zip 由发版上传，见 install checklist。 */
export const DEFAULT_HELPER_DOWNLOAD_URL = '/crosshub/downloads/CrossHub-Sync-Helper.zip'

/**
 * Sync Helper 安装包下载 URL。
 * - 未设置环境变量 → 默认占位路径
 * - 显式空 / `none` / `off` / `-` → 空字符串（UI 提示「请联系管理员获取安装包」）
 * - 其他非空 → 原样使用
 */
export function resolveHelperDownloadUrl() {
  const raw = import.meta.env.VITE_HELPER_DOWNLOAD_URL
  if (raw === undefined || raw === null) {
    return DEFAULT_HELPER_DOWNLOAD_URL
  }
  const trimmed = String(raw).trim()
  if (!trimmed || /^(none|off|-)$/i.test(trimmed)) {
    return ''
  }
  return trimmed
}
