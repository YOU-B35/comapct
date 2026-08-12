import { hasBackendSession } from './backendSession'
import { service } from './request'
import { WAREHOUSE_MENU_CODE } from '@/constants/employees'
import {
  deleteLocalEmployee,
  fetchLocalEmployees,
  saveLocalEmployee,
  toggleLocalEmployeeStatus,
} from './employeesLocal'

function mapMember(row) {
  if (!row) return row
  return {
    id: row.id,
    name: row.name,
    account: row.account,
    role: row.role,
    phone: row.phone || '',
    otherRole: row.other_role || row.otherRole || '',
    platforms: row.platforms || [],
    assignedStoreIds: row.assignedStoreIds || row.shop_ids || [],
    menuCodes: row.menu_codes || row.menuCodes || [],
    status: row.status !== false,
    boundAt: row.boundAt || row.bound_at || '',
  }
}

function toMemberPayload(payload) {
  const menuCodes = Array.isArray(payload.menuCodes)
    ? payload.menuCodes.filter((code) => code === WAREHOUSE_MENU_CODE)
    : []
  const body = {
    name: payload.name,
    account: payload.account,
    phone: payload.phone || '',
    role: payload.role,
    other_role: payload.otherRole || '',
    platforms: payload.platforms || [],
    shop_ids: payload.assignedStoreIds || [],
    menu_codes: menuCodes,
    status: payload.status !== false,
  }
  if (payload.password) body.password = payload.password
  return body
}

export function canUseTenantMembersBackend(auth) {
  return hasBackendSession(auth) && Boolean(auth?.isBoss)
}

async function fetchBackendMembers() {
  const res = await service.get('/api/tenant/members')
  const rows = res?.data || []
  return { success: true, data: rows.map(mapMember) }
}

export async function fetchAssignableMenus(auth) {
  if (canUseTenantMembersBackend(auth)) {
    const res = await service.get('/api/tenant/assignable-menus')
    return { success: true, data: res?.data || [] }
  }
  return {
    success: true,
    data: [{ code: WAREHOUSE_MENU_CODE, label: '仓库下单', group: 'warehouse' }],
  }
}

export async function fetchEmployees(auth) {
  if (canUseTenantMembersBackend(auth)) {
    return await fetchBackendMembers()
  }
  return fetchLocalEmployees()
}

export async function saveEmployee(auth, payload) {
  if (canUseTenantMembersBackend(auth)) {
    const body = toMemberPayload(payload)
    const res = payload.id
      ? await service.put(`/api/tenant/members/${payload.id}`, body)
      : await service.post('/api/tenant/members', body)
    return { success: true, data: mapMember(res?.data) }
  }

  const result = saveLocalEmployee(payload)
  if (result.error) throw new Error(result.error)
  return result
}

export async function updateMemberScopes(auth, memberId, { platforms, assignedStoreIds, menuCodes }) {
  if (!canUseTenantMembersBackend(auth)) {
    throw new Error('当前环境无法更新员工权限范围')
  }
  const res = await service.put(`/api/tenant/members/${memberId}/scopes`, {
    platforms: platforms || [],
    shop_ids: assignedStoreIds || [],
    menu_codes: Array.isArray(menuCodes) ? menuCodes : [],
  })
  return { success: true, data: mapMember(res?.data) }
}

export async function deleteEmployee(auth, id) {
  if (canUseTenantMembersBackend(auth)) {
    await service.delete(`/api/tenant/members/${id}`)
    return { success: true }
  }

  const result = deleteLocalEmployee(id)
  if (result.error) throw new Error(result.error)
  return result
}

export async function toggleEmployeeStatus(auth, id, status) {
  if (canUseTenantMembersBackend(auth)) {
    const res = await service.patch(`/api/tenant/members/${id}/status`, { status })
    return { success: true, data: mapMember(res?.data) }
  }

  const result = toggleLocalEmployeeStatus(id, status)
  if (result.error) throw new Error(result.error)
  return result
}
