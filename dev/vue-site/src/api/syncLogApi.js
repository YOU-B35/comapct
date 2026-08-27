/**
 * 全平台统一「最近同步日志」（Java /api/sync-logs，读 agent_task）。
 */
import { service } from './request'

export async function fetchPlatformSyncLogs({ platform, limit = 30 } = {}) {
  const params = {}
  if (platform) params.platform = platform
  if (limit) params.limit = limit
  const res = await service.get('/api/sync-logs', { params, skipGlobalErrorToast: true })
  const data = res?.data ?? res ?? {}
  return Array.isArray(data?.items) ? data.items : []
}
