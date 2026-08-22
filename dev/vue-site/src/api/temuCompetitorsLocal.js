import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { DEMO_COMPETITORS } from '@/constants/temuCompetitors'
import { loadScoped, resolveTenantId, saveScoped } from '@/utils/tenantStorage'

const STORAGE_KEY = 'crosshub_temu_competitors'

function loadAll(tenantId = resolveTenantId()) {
  return loadScoped(tenantId, STORAGE_KEY, []) || []
}

function saveAll(competitors, tenantId = resolveTenantId()) {
  saveScoped(tenantId, STORAGE_KEY, competitors)
}

function createId() {
  return `comp_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

function normalizeUrl(url) {
  const trimmed = String(url || '').trim()
  if (!trimmed) return ''
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  return `https://${trimmed}`
}

function validateUrl(url) {
  try {
    const parsed = new URL(normalizeUrl(url))
    if (!parsed.hostname) return { error: '请输入有效的店铺网址' }
    return { url: parsed.href }
  } catch {
    return { error: '请输入有效的店铺网址' }
  }
}

/** 始终同步 Demo 竞店样本（按 id 覆盖更新） */
export function ensureDemoCompetitors() {
  const existing = loadAll()
  const demoById = Object.fromEntries(DEMO_COMPETITORS.map((c) => [c.id, c]))
  const custom = existing.filter((item) => !demoById[item.id])
  const now = nowUtc8String()
  const demos = DEMO_COMPETITORS.map((item) => ({
    ...item,
    lastAnalyzedAt: item.lastAnalyzedAt || now,
  }))
  saveAll([...custom, ...demos])
}

export function fetchLocalCompetitors() {
  ensureDemoCompetitors()
  return { success: true, data: loadAll() }
}

export function saveLocalCompetitor({ id, label, url }) {
  const validation = validateUrl(url)
  if (validation.error) return { error: validation.error }

  const name = String(label || '').trim()
  if (!name) return { error: '请填写店铺备注名称' }

  const competitors = loadAll()
  const duplicate = competitors.find(
    (item) => item.url === validation.url && item.id !== id,
  )
  if (duplicate) {
    return { error: `该网址已添加为「${duplicate.label}」` }
  }

  const now = nowUtc8String()

  if (id) {
    const index = competitors.findIndex((item) => item.id === id)
    if (index === -1) return { error: '竞争对手不存在' }
    competitors[index] = {
      ...competitors[index],
      label: name,
      url: validation.url,
      updatedAt: now,
    }
    saveAll(competitors)
    return { success: true, data: { ...competitors[index] } }
  }

  const row = {
    id: createId(),
    label: name,
    url: validation.url,
    createdAt: now,
    updatedAt: now,
    lastAnalyzedAt: null,
  }
  competitors.push(row)
  saveAll(competitors)
  return { success: true, data: { ...row } }
}

export function deleteLocalCompetitor(id) {
  const competitors = loadAll()
  const index = competitors.findIndex((item) => item.id === id)
  if (index === -1) return { error: '竞争对手不存在' }
  const [removed] = competitors.splice(index, 1)
  saveAll(competitors)
  return { success: true, data: removed }
}

export function markCompetitorAnalyzed(id) {
  const competitors = loadAll()
  const index = competitors.findIndex((item) => item.id === id)
  if (index === -1) return
  const now = nowUtc8String()
  competitors[index] = { ...competitors[index], lastAnalyzedAt: now }
  saveAll(competitors)
}
