import {
  analyzeBackendCompetitors,
  deleteBackendCompetitor,
  discoverBackendCompetitors,
  downloadBackendCompetitorReport,
  fetchBackendCompetitorReports,
  fetchBackendCompetitors,
  saveBackendCompetitor,
} from './temuCompetitorsApi'
import { useAuthStore } from '@/stores/auth'
import { hasBackendSession } from './backendSession'
import {
  deleteLocalCompetitor,
  ensureDemoCompetitors,
  fetchLocalCompetitors,
  markCompetitorAnalyzed,
  saveLocalCompetitor,
} from './temuCompetitorsLocal'
import {
  deleteCompetitorSnapshots,
  getLatestSnapshot,
  resetCompetitorSnapshots,
} from './temuCompetitorSnapshotsLocal'
import { buildCompetitorMonitorReport } from '@/utils/temuCompetitor'

function canUseBackend() {
  return hasBackendSession(useAuthStore())
}

function loadAllCompetitors() {
  ensureDemoCompetitors()
  return fetchLocalCompetitors().data || []
}

function resolveTargets(competitors) {
  const all = loadAllCompetitors()
  if (!competitors?.length) return all
  const ids = new Set(competitors.map((item) => item.id))
  return all.filter((item) => ids.has(item.id))
}

function buildReportsForCompetitors(competitors) {
  return (competitors || [])
    .map((competitor) => buildCompetitorMonitorReport(competitor))
    .filter(Boolean)
}

export function fetchCompetitors() {
  if (canUseBackend()) return fetchBackendCompetitors()
  return fetchLocalCompetitors()
}

export function saveCompetitor(payload) {
  if (canUseBackend()) return saveBackendCompetitor(payload)
  const result = saveLocalCompetitor(payload)
  if (result.error) throw new Error(result.error)
  return result
}

export function deleteCompetitor(id) {
  if (canUseBackend()) return deleteBackendCompetitor(id)
  deleteCompetitorSnapshots(id)
  const result = deleteLocalCompetitor(id)
  if (result.error) throw new Error(result.error)
  return result
}

/** 读取已有快照生成报告，缺失时自动补 Demo 快照 */
export function fetchCompetitorReports(competitors) {
  if (canUseBackend()) return fetchBackendCompetitorReports()
  const targets = resolveTargets(competitors)
  for (const competitor of targets) {
    if (!getLatestSnapshot(competitor.id)) {
      resetCompetitorSnapshots(competitor)
    }
  }
  const reports = buildReportsForCompetitors(targets)
  return { success: true, data: reports, competitors: targets }
}

export function discoverCompetitors(payload = {}) {
  if (canUseBackend()) return discoverBackendCompetitors(payload)
  const candidates = [
    {
      rank: 1,
      label: 'fishing tackle 搜索结果候选源',
      url: 'https://www.temu.com/za/search_result.html?search_key=fishing%20tackle',
      host: 'www.temu.com',
      sourceKeyword: 'fishing tackle',
      sourceType: 'search',
      sampleProductCount: 10,
      sampleProducts: [
        { name: 'Fishing Lure Set', price: 5.99, salesSignal: 1200, url: 'https://www.temu.com/za/fishing-lure-demo' },
        { name: 'Fishing Hooks Kit', price: 3.49, salesSignal: 500, url: 'https://www.temu.com/za/fishing-hooks-demo' },
      ],
      crawlable: true,
    },
  ]
  return {
    success: true,
    data: {
      keyword: payload.keyword || 'fishing tackle',
      region: payload.region || 'za',
      searchUrl: candidates[0].url,
      candidates,
    },
  }
}

/** 每日爬取：为列表中每个竞店重建快照并生成报告 */
export function analyzeCompetitors(competitors, options = {}) {
  if (canUseBackend()) return analyzeBackendCompetitors(competitors, options)
  const targets = resolveTargets(competitors)
  if (!targets.length) {
    return { success: true, data: [], competitors: [] }
  }

  for (const competitor of targets) {
    resetCompetitorSnapshots(competitor)
  }

  const reports = buildReportsForCompetitors(targets)
  for (const report of reports) {
    markCompetitorAnalyzed(report.id)
  }
  return { success: true, data: reports, competitors: targets }
}

export async function exportCompetitorReport(report) {
  if (canUseBackend()) return downloadBackendCompetitorReport(report)
  throw new Error('当前仅后端模式支持导出 Excel 报表')
}
