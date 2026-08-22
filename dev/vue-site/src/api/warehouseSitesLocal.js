import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import {
  WAREHOUSE_SITES_SEED,
  WAREHOUSE_SITES_STORAGE_KEY,
} from '@/constants/warehouseSites'
import { loadScoped, resolveTenantId, saveScoped, isDemoTemplateEnabled } from '@/utils/tenantStorage'

function loadAll(tenantId = resolveTenantId()) {
  return loadScoped(tenantId, WAREHOUSE_SITES_STORAGE_KEY, []) || []
}

function saveAll(sites, tenantId = resolveTenantId()) {
  saveScoped(tenantId, WAREHOUSE_SITES_STORAGE_KEY, sites)
}

function createId() {
  return `wh_site_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

export function ensureDemoWarehouseSites(tenantId = resolveTenantId()) {
  if (!isDemoTemplateEnabled(tenantId)) return
  const existing = loadAll(tenantId)
  const seedById = Object.fromEntries(WAREHOUSE_SITES_SEED.map((item) => [item.id, item]))
  const custom = existing.filter((item) => !seedById[item.id])
  saveAll([...custom, ...WAREHOUSE_SITES_SEED.map((item) => ({ ...item }))], tenantId)
}

export function fetchLocalWarehouseSites({ activeOnly = false } = {}) {
  ensureDemoWarehouseSites()
  let sites = loadAll()
  if (activeOnly) {
    sites = sites.filter((item) => item.status !== false)
  }
  return {
    success: true,
    data: sites.sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0)),
  }
}

export function findLocalWarehouseSite(id) {
  ensureDemoWarehouseSites()
  return loadAll().find((item) => item.id === id) || null
}

function validateSiteInput({ name, code, id, sites }) {
  const siteName = String(name || '').trim()
  const siteCode = String(code || '').trim().toLowerCase()
  if (!siteName) return { error: '请填写仓库名称' }
  if (!siteCode) return { error: '请填写仓库编码' }
  const duplicate = sites.find(
    (item) => item.code?.toLowerCase() === siteCode && item.id !== id,
  )
  if (duplicate) return { error: `编码已被「${duplicate.name}」使用` }
  return { name: siteName, code: siteCode }
}

export function saveLocalWarehouseSite(payload) {
  const sites = loadAll()
  const { id, address, status, sortOrder } = payload
  const validation = validateSiteInput({ ...payload, sites })
  if (validation.error) return { error: validation.error }

  const now = nowUtc8String()
  if (id) {
    const index = sites.findIndex((item) => item.id === id)
    if (index === -1) return { error: '仓库不存在' }
    sites[index] = {
      ...sites[index],
      name: validation.name,
      code: validation.code,
      address: String(address || '').trim(),
      status: status !== false,
      sortOrder: Number(sortOrder) || sites[index].sortOrder || 0,
    }
  } else {
    sites.push({
      id: createId(),
      name: validation.name,
      code: validation.code,
      address: String(address || '').trim(),
      status: status !== false,
      sortOrder: Number(sortOrder) || sites.length * 10 + 10,
      createdAt: now,
    })
  }

  saveAll(sites)
  return { success: true }
}

export function deleteLocalWarehouseSite(id) {
  const sites = loadAll()
  const index = sites.findIndex((item) => item.id === id)
  if (index === -1) return { error: '仓库不存在' }
  sites.splice(index, 1)
  saveAll(sites)
  return { success: true }
}

export function toggleLocalWarehouseSiteStatus(id, status) {
  const sites = loadAll()
  const index = sites.findIndex((item) => item.id === id)
  if (index === -1) return { error: '仓库不存在' }
  sites[index] = { ...sites[index], status: status !== false }
  saveAll(sites)
  return { success: true }
}
