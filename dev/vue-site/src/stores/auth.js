import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { clearAccessToken, fetchBackendSession } from '@/api/request'
import { resolveSidebarMenus, flattenMenuPaths } from '@/utils/menuAuth'
import { resolveWarehouseNames } from '@/utils/warehouseScope'
import { usePlatformSyncStore } from '@/stores/platformSync'

function readJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

export const useAuthStore = defineStore('auth', () => {
  const isLoggedIn = ref(localStorage.getItem('crosshub_logged_in') === '1')
  const role = ref(localStorage.getItem('crosshub_role') || 'boss')
  const company = ref(
    readJson('crosshub_company', {
      name: '泰州亿拓户外用品有限公司',
      account: 'admin@crosshub.cn',
    }),
  )
  const employee = ref(
    readJson('crosshub_employee', {
      id: '',
      name: '',
      account: '',
      role: '',
      platforms: [],
      assignedStoreIds: [],
    }),
  )
  const warehouse = ref(
    readJson('crosshub_warehouse', {
      id: '',
      name: '',
      account: '',
      role: '',
    }),
  )
  const backendLinked = ref(localStorage.getItem('backend_linked') === '1')
  const backendUserId = ref(Number(localStorage.getItem('backend_user_id') || 0) || null)
  const backendRole = ref(localStorage.getItem('backend_role') || '')
  const tenantId = ref(
    Number(localStorage.getItem('backend_tenant_id') || localStorage.getItem('crosshub_local_tenant_id') || 0) || null,
  )
  const menus = ref(readJson('crosshub_menus', []))
  const platforms = ref(readJson('crosshub_platforms', []))
  const shopScope = ref(readJson('crosshub_shop_scope', []))
  const warehouseScope = ref(readJson('crosshub_warehouse_scope', []))
  const warehouseScopeNames = ref(readJson('crosshub_warehouse_scope_names', []))
  const teamLeader = ref(localStorage.getItem('crosshub_team_leader') === '1')
  const teamId = ref(Number(localStorage.getItem('crosshub_team_id') || 0) || null)
  const teamName = ref(localStorage.getItem('crosshub_team_name') || '')
  const per = ref(localStorage.getItem('crosshub_per') || '')

  const isBoss = computed(() => role.value === 'boss')
  const isEmployee = computed(() => role.value === 'employee')
  const isWarehouse = computed(() => role.value === 'warehouse')
  const isTeamLeader = computed(() => Boolean(teamLeader.value))
  const portalLabel = computed(() => {
    if (isBoss.value) return '企业管理员'
    if (isWarehouse.value) return '仓库端口'
    return '员工端口'
  })
  const displayName = computed(() => {
    if (isBoss.value) return company.value.name
    if (isWarehouse.value) return warehouse.value.name
    return employee.value.name
  })
  const sidebarMenus = computed(() => resolveSidebarMenus({
    menus: menus.value,
    isBoss: isBoss.value,
    isEmployee: isEmployee.value,
    isWarehouse: isWarehouse.value,
    backendLinked: backendLinked.value,
    employee: employee.value,
    warehouse: warehouse.value,
    platforms: platforms.value,
    role: role.value,
  }))
  const assignedWarehouseLabels = computed(() => {
    if (warehouseScopeNames.value.length) return warehouseScopeNames.value
    if (warehouse.value.warehouseNames?.length) return warehouse.value.warehouseNames
    return resolveWarehouseNames(warehouseScope.value.length
      ? warehouseScope.value
      : warehouse.value.warehouseIds || [])
  })
  const menuPaths = computed(() => flattenMenuPaths(sidebarMenus.value))

  function persistSession() {
    localStorage.setItem('crosshub_logged_in', isLoggedIn.value ? '1' : '0')
    localStorage.setItem('crosshub_role', role.value)
    localStorage.setItem('crosshub_company', JSON.stringify(company.value))
    localStorage.setItem('crosshub_employee', JSON.stringify(employee.value))
    localStorage.setItem('crosshub_warehouse', JSON.stringify(warehouse.value))
    localStorage.setItem('backend_linked', backendLinked.value ? '1' : '0')
    localStorage.setItem('backend_role', backendRole.value || '')
    localStorage.setItem('crosshub_menus', JSON.stringify(menus.value))
    localStorage.setItem('crosshub_platforms', JSON.stringify(platforms.value))
    localStorage.setItem('crosshub_shop_scope', JSON.stringify(shopScope.value))
    localStorage.setItem('crosshub_warehouse_scope', JSON.stringify(warehouseScope.value))
    localStorage.setItem('crosshub_warehouse_scope_names', JSON.stringify(warehouseScopeNames.value))
    localStorage.setItem('crosshub_team_leader', teamLeader.value ? '1' : '0')
    if (teamId.value) localStorage.setItem('crosshub_team_id', String(teamId.value))
    else localStorage.removeItem('crosshub_team_id')
    localStorage.setItem('crosshub_team_name', teamName.value || '')
    if (per.value !== '' && per.value != null) localStorage.setItem('crosshub_per', String(per.value))
    else localStorage.removeItem('crosshub_per')
    if (backendUserId.value) {
      localStorage.setItem('backend_user_id', String(backendUserId.value))
    } else {
      localStorage.removeItem('backend_user_id')
    }
    if (tenantId.value) {
      localStorage.setItem('backend_tenant_id', String(tenantId.value))
    } else {
      localStorage.removeItem('backend_tenant_id')
    }
  }

  function applyBackendSession(payload = {}) {
    menus.value = Array.isArray(payload.menus) ? payload.menus : []
    platforms.value = Array.isArray(payload.platforms) ? payload.platforms : []
    shopScope.value = Array.isArray(payload.shop_scope) ? payload.shop_scope : []
    warehouseScope.value = Array.isArray(payload.warehouse_scope) ? payload.warehouse_scope : []
    warehouseScopeNames.value = Array.isArray(payload.warehouse_scope_names)
      ? payload.warehouse_scope_names
      : resolveWarehouseNames(warehouseScope.value)
    if (payload.tenant_id) tenantId.value = payload.tenant_id
    if (payload.user_id) backendUserId.value = payload.user_id
    if (payload.role) backendRole.value = payload.role
    teamLeader.value = Boolean(payload.team_leader)
    teamId.value = payload.team_id || null
    teamName.value = payload.team_name || ''
    if (payload.per != null && payload.per !== '') per.value = String(payload.per)
    backendLinked.value = true
    persistSession()
  }

  function applyLocalSession() {
    backendLinked.value = false
    backendRole.value = ''
    backendUserId.value = null
    tenantId.value = null
    menus.value = []
    platforms.value = []
    shopScope.value = []
    warehouseScope.value = []
    warehouseScopeNames.value = []
    clearAccessToken()
  }

  function setCompany(payload) {
    if (payload.backendLinked === false) applyLocalSession()
    company.value = {
      name: payload.company || payload.name,
      account: payload.account,
    }
    if (payload.backendRole) backendRole.value = payload.backendRole
    if (payload.backendUserId) backendUserId.value = payload.backendUserId
    if (payload.backendLinked !== undefined) backendLinked.value = Boolean(payload.backendLinked)
    if (payload.menus) menus.value = payload.menus
    if (payload.platforms) platforms.value = payload.platforms
    if (payload.shop_scope) shopScope.value = payload.shop_scope
    if (payload.warehouse_scope) warehouseScope.value = payload.warehouse_scope
    if (payload.tenant_id) tenantId.value = payload.tenant_id
    persistSession()
  }

  function setWarehouse(payload) {
    if (payload.backendLinked === false) applyLocalSession()
    const scopeIds = payload.warehouseIds || payload.warehouse_scope || []
    const scopeNames = payload.warehouse_scope_names
      || payload.warehouseNames
      || resolveWarehouseNames(scopeIds)
    warehouse.value = {
      id: payload.id || '',
      name: payload.name,
      account: payload.account,
      role: payload.role,
      phone: payload.phone || '',
      warehouseIds: scopeIds,
      warehouseNames: scopeNames,
    }
    if (payload.backendRole) backendRole.value = payload.backendRole
    if (payload.backendUserId) backendUserId.value = payload.backendUserId
    if (payload.backendLinked !== undefined) backendLinked.value = Boolean(payload.backendLinked)
    if (payload.menus) menus.value = payload.menus
    if (payload.warehouse_scope) warehouseScope.value = payload.warehouse_scope
    if (payload.warehouse_scope_names) warehouseScopeNames.value = payload.warehouse_scope_names
    else if (payload.warehouse_scope) warehouseScopeNames.value = resolveWarehouseNames(payload.warehouse_scope)
    if (payload.tenant_id) tenantId.value = payload.tenant_id
    warehouseScope.value = scopeIds
    warehouseScopeNames.value = scopeNames
    persistSession()
  }

  function setEmployee(payload) {
    if (payload.backendLinked === false) applyLocalSession()
    employee.value = {
      id: payload.id || '',
      name: payload.name,
      account: payload.account,
      role: payload.role,
      otherRole: payload.otherRole || payload.other_role || '',
      platforms: payload.platforms || [],
      assignedStoreIds: payload.assignedStoreIds || payload.shop_scope || [],
      menuCodes: payload.menuCodes || payload.menu_codes || [],
    }
    if (payload.backendRole) backendRole.value = payload.backendRole
    if (payload.backendUserId) backendUserId.value = payload.backendUserId
    if (payload.backendLinked !== undefined) backendLinked.value = Boolean(payload.backendLinked)
    if (payload.menus) menus.value = payload.menus
    if (payload.platforms) platforms.value = payload.platforms
    if (payload.shop_scope) shopScope.value = payload.shop_scope
    if (payload.tenant_id) tenantId.value = payload.tenant_id
    if (payload.team_leader !== undefined) teamLeader.value = Boolean(payload.team_leader)
    if (payload.team_id !== undefined) teamId.value = payload.team_id || null
    if (payload.team_name !== undefined) teamName.value = payload.team_name || ''
    persistSession()
  }

  function hasMenuCode(code) {
    return menus.value.some((item) => item.code === code)
  }

  async function refreshSession() {
    if (!backendLinked.value) return
    const data = await fetchBackendSession()
    applyBackendSession(data)
    if (!isBoss.value && data) {
      if (isWarehouse.value) {
        const scopeIds = data.warehouse_scope || warehouse.value.warehouseIds || []
        const scopeNames = data.warehouse_scope_names || resolveWarehouseNames(scopeIds)
        warehouse.value = {
          ...warehouse.value,
          warehouseIds: scopeIds,
          warehouseNames: scopeNames,
        }
        warehouseScope.value = scopeIds
        warehouseScopeNames.value = scopeNames
      } else {
        employee.value = {
          ...employee.value,
          otherRole: data.other_role || employee.value.otherRole || '',
          platforms: data.platforms || employee.value.platforms,
          assignedStoreIds: data.shop_scope || employee.value.assignedStoreIds,
        }
      }
      persistSession()
    }
  }

  function login(nextRole) {
    usePlatformSyncStore().resetSession()
    role.value = nextRole
    isLoggedIn.value = true
    persistSession()
  }

  function setPer(nextPer) {
    per.value = nextPer == null ? '' : String(nextPer)
    persistSession()
  }

  function logout() {
    usePlatformSyncStore().resetSession()
    isLoggedIn.value = false
    backendLinked.value = false
    backendRole.value = ''
    backendUserId.value = null
    tenantId.value = null
    per.value = ''
    menus.value = []
    platforms.value = []
    shopScope.value = []
    warehouseScope.value = []
    warehouseScopeNames.value = []
    warehouse.value = { id: '', name: '', account: '', role: '', warehouseIds: [], warehouseNames: [] }
    clearAccessToken()
    localStorage.removeItem('crosshub_logged_in')
    localStorage.removeItem('backend_linked')
    localStorage.removeItem('backend_role')
    localStorage.removeItem('backend_user_id')
    localStorage.removeItem('backend_tenant_id')
    localStorage.removeItem('crosshub_per')
    localStorage.removeItem('crosshub_menus')
    localStorage.removeItem('crosshub_platforms')
    localStorage.removeItem('crosshub_shop_scope')
    localStorage.removeItem('crosshub_warehouse_scope')
    localStorage.removeItem('crosshub_warehouse_scope_names')
    localStorage.removeItem('crosshub_team_leader')
    localStorage.removeItem('crosshub_team_id')
    localStorage.removeItem('crosshub_team_name')
  }

  return {
    isLoggedIn,
    role,
    per,
    company,
    employee,
    warehouse,
    backendLinked,
    backendUserId,
    backendRole,
    tenantId,
    menus,
    platforms,
    shopScope,
    warehouseScope,
    warehouseScopeNames,
    teamLeader,
    teamId,
    teamName,
    assignedWarehouseLabels,
    isBoss,
    isEmployee,
    isWarehouse,
    isTeamLeader,
    portalLabel,
    displayName,
    sidebarMenus,
    menuPaths,
    setCompany,
    setEmployee,
    setWarehouse,
    setPer,
    applyBackendSession,
    hasMenuCode,
    refreshSession,
    login,
    logout,
  }
})
