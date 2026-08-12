import { DEMO_EMPLOYEES } from '@/constants/employees'
import { validateStoreAssignmentConflict } from '@/utils/storeAssignment'
import { loadScoped, resolveTenantId, saveScoped, isDemoTemplateEnabled } from '@/utils/tenantStorage'

const STORAGE_KEY = 'crosshub_employees'

function loadAll(tenantId = resolveTenantId()) {
  return loadScoped(tenantId, STORAGE_KEY, []) || []
}

function saveAll(employees, tenantId = resolveTenantId()) {
  saveScoped(tenantId, STORAGE_KEY, employees)
}

function createId() {
  return `emp_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

/** 始终同步 Demo 员工样本（按 id 覆盖更新，保留已编辑字段） */
export function ensureDemoEmployees(tenantId = resolveTenantId()) {
  if (!isDemoTemplateEnabled(tenantId)) return
  const existing = loadAll(tenantId)
  const demoById = Object.fromEntries(DEMO_EMPLOYEES.map((e) => [e.id, e]))
  const custom = existing.filter((item) => !demoById[item.id])
  const mergedDemos = DEMO_EMPLOYEES.map((item) => {
    const current = existing.find((row) => row.id === item.id)
    if (!current) return { ...item }
    return {
      ...item,
      ...current,
      password: current.password || item.password,
    }
  })
  saveAll([...custom, ...mergedDemos], tenantId)
}

function validateEmployeeInput({ name, account, role, platforms, password, id, employees }) {
  const empName = String(name || '').trim()
  const acc = String(account || '').trim()
  const empRole = String(role || '').trim()
  const pwd = String(password || '')
  const platformList = Array.isArray(platforms) ? platforms.filter(Boolean) : []

  if (!empName) return { error: '请填写员工姓名' }
  if (!acc) return { error: '请填写登录账号' }
  if (!empRole) return { error: '请选择岗位角色' }
  if (!platformList.length) return { error: '请至少选择一个负责平台' }
  if (!id && !pwd) return { error: '请设置初始登录密码' }

  const duplicate = employees.find(
    (item) => item.account === acc && item.id !== id,
  )
  if (duplicate) {
    return { error: `登录账号已被「${duplicate.name}」使用` }
  }

  return {
    name: empName,
    account: acc,
    role: empRole,
    platforms: platformList,
    password: pwd,
  }
}

export function fetchLocalEmployees() {
  ensureDemoEmployees()
  return { success: true, data: loadAll() }
}

export function saveLocalEmployee(payload) {
  const employees = loadAll()
  const { id, phone, status, assignedStoreIds, menuCodes } = payload
  const validation = validateEmployeeInput({ ...payload, employees })
  if (validation.error) return { error: validation.error }

  const storeIds = Array.isArray(assignedStoreIds)
    ? [...new Set(assignedStoreIds.filter(Boolean))]
    : []
  const storeConflict = validateStoreAssignmentConflict(employees, storeIds, id)
  if (storeConflict) return { error: storeConflict }

  const codes = Array.isArray(menuCodes)
    ? menuCodes.filter((code) => code === 'employee.warehouse')
    : []
  const boundAt = new Date().toISOString().replace('T', ' ').slice(0, 19)

  if (id) {
    const index = employees.findIndex((item) => item.id === id)
    if (index === -1) return { error: '员工不存在' }
    employees[index] = {
      ...employees[index],
      name: validation.name,
      account: validation.account,
      role: validation.role,
      otherRole: String(payload.otherRole || '').trim(),
      platforms: validation.platforms,
      assignedStoreIds: storeIds,
      menuCodes: codes,
      phone: String(phone || '').trim(),
      status: status !== false,
      password: validation.password || employees[index].password,
      boundAt,
    }
    saveAll(employees)
    return { success: true, data: { ...employees[index] } }
  }

  const row = {
    id: createId(),
    name: validation.name,
    account: validation.account,
    role: validation.role,
    otherRole: String(payload.otherRole || '').trim(),
    platforms: validation.platforms,
    assignedStoreIds: storeIds,
    menuCodes: codes,
    phone: String(phone || '').trim(),
    password: validation.password,
    status: status !== false,
    boundAt,
  }
  employees.push(row)
  saveAll(employees)
  return { success: true, data: { ...row } }
}

export function deleteLocalEmployee(id) {
  const employees = loadAll()
  const index = employees.findIndex((item) => item.id === id)
  if (index === -1) return { error: '员工不存在' }
  const [removed] = employees.splice(index, 1)
  saveAll(employees)
  return { success: true, data: removed }
}

export function toggleLocalEmployeeStatus(id, status) {
  const employees = loadAll()
  const index = employees.findIndex((item) => item.id === id)
  if (index === -1) return { error: '员工不存在' }
  employees[index] = { ...employees[index], status }
  saveAll(employees)
  return { success: true, data: employees[index] }
}
