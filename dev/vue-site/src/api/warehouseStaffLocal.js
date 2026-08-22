import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { WAREHOUSE_DEFAULT_ROLE, WAREHOUSE_USERS, WAREHOUSE_STAFF_STORAGE_KEY } from '@/constants/warehouseStaff'
import { loadScoped, resolveTenantId, saveScoped, isDemoTemplateEnabled } from '@/utils/tenantStorage'

function loadAll(tenantId = resolveTenantId()) {
  return loadScoped(tenantId, WAREHOUSE_STAFF_STORAGE_KEY, []) || []
}

function saveAll(staff, tenantId = resolveTenantId()) {
  saveScoped(tenantId, WAREHOUSE_STAFF_STORAGE_KEY, staff)
}

function createId() {
  return `wh_staff_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

/** 始终同步 Demo 仓库人员样本（按 id 覆盖更新） */
export function ensureDemoWarehouseStaff(tenantId = resolveTenantId()) {
  if (!isDemoTemplateEnabled(tenantId)) return
  const existing = loadAll(tenantId)
  const demoById = Object.fromEntries(WAREHOUSE_USERS.map((item) => [item.id, item]))
  const custom = existing.filter((item) => !demoById[item.id])
  saveAll([...custom, ...WAREHOUSE_USERS.map((item) => ({ ...item }))], tenantId)
}

export function fetchLocalWarehouseStaff() {
  ensureDemoWarehouseStaff()
  return { success: true, data: loadAll() }
}

export function findLocalWarehouseStaffByAccount(account) {
  ensureDemoWarehouseStaff()
  const acc = String(account || '').trim().toLowerCase()
  return loadAll().find(
    (item) => item.account.toLowerCase() === acc && item.status !== false,
  )
}

function validateStaffInput({ name, account, role, password, id, staff }) {
  const staffName = String(name || '').trim()
  const acc = String(account || '').trim()
  const staffRole = String(role || WAREHOUSE_DEFAULT_ROLE).trim()
  const pwd = String(password || '')

  if (!staffName) return { error: '请填写员工姓名' }
  if (!acc) return { error: '请填写登录账号' }
  if (!staffRole) return { error: '岗位无效' }
  if (!id && !pwd) return { error: '请设置初始登录密码' }

  const duplicate = staff.find((item) => item.account === acc && item.id !== id)
  if (duplicate) {
    return { error: `登录账号已被「${duplicate.name}」使用` }
  }

  return { name: staffName, account: acc, role: staffRole, password: pwd }
}

export function saveLocalWarehouseStaff(payload) {
  const staff = loadAll()
  const { id, phone, status } = payload
  const validation = validateStaffInput({ ...payload, staff })
  if (validation.error) return { error: validation.error }

  const now = nowUtc8String()
  if (id) {
    const index = staff.findIndex((item) => item.id === id)
    if (index === -1) return { error: '仓库人员不存在' }
    staff[index] = {
      ...staff[index],
      name: validation.name,
      account: validation.account,
      role: validation.role,
      phone: String(phone || '').trim(),
      status: status !== false,
      warehouseIds: Array.isArray(payload.warehouseIds) ? [...payload.warehouseIds] : staff[index].warehouseIds || [],
      ...(validation.password ? { password: validation.password } : {}),
    }
  } else {
    staff.push({
      id: createId(),
      name: validation.name,
      account: validation.account,
      password: validation.password,
      role: validation.role,
      phone: String(phone || '').trim(),
      status: status !== false,
      warehouseIds: Array.isArray(payload.warehouseIds) ? [...payload.warehouseIds] : [],
      boundAt: now,
    })
  }

  saveAll(staff)
  return { success: true }
}

export function deleteLocalWarehouseStaff(id) {
  const staff = loadAll()
  const index = staff.findIndex((item) => item.id === id)
  if (index === -1) return { error: '仓库人员不存在' }
  staff.splice(index, 1)
  saveAll(staff)
  return { success: true }
}

export function toggleLocalWarehouseStaffStatus(id, status) {
  const staff = loadAll()
  const index = staff.findIndex((item) => item.id === id)
  if (index === -1) return { error: '仓库人员不存在' }
  staff[index] = { ...staff[index], status: status !== false }
  saveAll(staff)
  return { success: true }
}
