import { isTemuBackendEnabled } from './config'
import { backendLogin, clearAccessToken, service } from './request'
import { resolveWarehouseNames } from '@/utils/warehouseScope'

function mapBackendSession(backend) {
  if (!backend) return {}
  return {
    backendLinked: true,
    backendUserId: backend.user_id,
    backendRole: backend.role,
    tenant_id: backend.tenant_id,
    menus: backend.menus || [],
    platforms: backend.platforms || [],
    shop_scope: backend.shop_scope || [],
    warehouse_scope: backend.warehouse_scope || [],
    warehouse_scope_names: backend.warehouse_scope_names || [],
    team_leader: Boolean(backend.team_leader),
    team_id: backend.team_id || null,
    team_name: backend.team_name || '',
    per: backend.per == null || backend.per === '' ? '' : String(backend.per),
    portal_role: backend.portal_role || '',
    landing_path: backend.landing_path || '',
  }
}

async function requireBackendLogin(account, password, portalRole) {
  try {
    return await backendLogin(account, password, portalRole)
  } catch (err) {
    const msg = err?.message || '登录失败，请检查账号密码后重试'
    const wrapped = new Error(msg)
    if (err?.errorCode) wrapped.errorCode = err.errorCode
    throw wrapped
  }
}

/**
 * 统一登录：后端按账号 per（0=boss / 1=员工 / 2=仓库）自动校准 portal 与落地页。
 * preferredPortal 仅前端选项卡提示，不覆盖后端校准结果。
 */
export async function loginAccount({ account, password, preferredPortal }) {
  const acc = String(account || '').trim()
  const pwd = String(password || '')
  const portalHint = String(preferredPortal || '').trim().toLowerCase()

  if (isTemuBackendEnabled()) {
    // portal_role 可选；后端按账号 per 自动校准
    const backend = await requireBackendLogin(acc, pwd, portalHint || undefined)
    const portal = String(backend.portal_role || '').toLowerCase()
    const session = mapBackendSession(backend)
    const landingFallback =
      portal === 'boss'
        ? '/boss/dashboard'
        : portal === 'warehouse'
          ? '/warehouse/pending-review'
          : '/employee/dashboard'
    if (portal === 'boss') {
      return {
        success: true,
        portal: 'boss',
        per: String(backend.per ?? '0'),
        landingPath: backend.landing_path || landingFallback,
        data: {
          company: backend.company || backend.nickname || '企业',
          account: backend.account || acc,
          ...session,
        },
      }
    }
    if (portal === 'warehouse') {
      return {
        success: true,
        portal: 'warehouse',
        per: String(backend.per ?? '2'),
        landingPath: backend.landing_path || landingFallback,
        data: {
          id: String(backend.user_id),
          name: backend.nickname || backend.account || acc,
          account: backend.account || acc,
          role: backend.job_title || '仓库管理员',
          phone: '',
          ...session,
        },
      }
    }
    return {
      success: true,
      portal: 'employee',
      per: String(backend.per ?? '1'),
      landingPath: backend.landing_path || landingFallback,
      data: {
        id: backend.user_id,
        name: backend.nickname || backend.account || acc,
        account: backend.account || acc,
        role: backend.job_title || backend.role || '',
        otherRole: backend.other_role || '',
        platforms: backend.platforms || [],
        assignedStoreIds: backend.shop_scope || [],
        ...session,
      },
    }
  }

  // 本地 mock：仍按账号尝试 boss → warehouse → employee
  try {
    const boss = await loginBoss({ account: acc, password: pwd })
    return { success: true, portal: 'boss', landingPath: '/boss/dashboard', data: boss.data }
  } catch (_) {
    /* try next */
  }
  try {
    const wh = await loginWarehouse({ account: acc, password: pwd })
    return { success: true, portal: 'warehouse', landingPath: '/warehouse/pending-review', data: wh.data }
  } catch (_) {
    /* try next */
  }
  const emp = await loginEmployee({ account: acc, password: pwd })
  return { success: true, portal: 'employee', landingPath: '/employee/dashboard', data: emp.data }
}

export async function registerCompany(payload) {
  const company = String(payload.company || '').trim()
  const account = String(payload.account || '').trim()
  const password = String(payload.password || '')

  if (isTemuBackendEnabled()) {
    const res = await service.post('/api/auth/register', {
      company,
      account,
      password,
    })
    const data = res?.data ?? res
    if (!data?.tenant_id) {
      throw new Error('注册失败：未返回租户信息')
    }
    return { success: true, data }
  }

  const { registerLocalUser } = await import('./authLocal')
  const result = registerLocalUser({ company, account, password })
  if (result.error) throw new Error(result.error)
  return result
}

/** 员工自助注册：加入已有企业（企业名称或邀请码） */
export async function registerEmployee(payload) {
  const company = String(payload.company || '').trim()
  const tenantCode = String(payload.tenantCode || payload.tenant_code || '').trim()
  const account = String(payload.account || '').trim()
  const password = String(payload.password || '')
  const name = String(payload.name || '').trim() || account

  if (isTemuBackendEnabled()) {
    const res = await service.post('/api/auth/register-employee', {
      company,
      tenant_code: tenantCode,
      account,
      password,
      name,
    })
    const data = res?.data ?? res
    if (!data?.tenant_id && !data?.user_id) {
      throw new Error('注册失败：未返回用户信息')
    }
    return { success: true, data }
  }

  const { registerLocalEmployee } = await import('./authLocal')
  const result = registerLocalEmployee({ company, tenantCode, account, password, name })
  if (result.error) throw new Error(result.error)
  return result
}

export async function loginBoss(payload) {
  const account = String(payload.account || '').trim()
  const password = String(payload.password || '')

  if (isTemuBackendEnabled()) {
    const backend = await requireBackendLogin(account, password, 'boss')
    return {
      success: true,
      data: {
        company: backend.company || backend.nickname || '企业',
        account: backend.account || account,
        ...mapBackendSession(backend),
      },
    }
  }

  const { loginLocalBoss } = await import('./authLocal')
  const result = loginLocalBoss({ account, password })
  if (result.error) throw new Error(result.error)
  clearAccessToken()
  return {
    success: true,
    data: {
      company: result.data.company,
      account: result.data.account,
      tenant_id: result.data.tenant_id || null,
      backendLinked: false,
      menus: [],
      platforms: [],
      shop_scope: [],
      warehouse_scope: [],
    },
  }
}

export async function loginEmployee({ account, password }) {
  if (isTemuBackendEnabled()) {
    const backend = await requireBackendLogin(account, password, 'employee')
    return {
      success: true,
      data: {
        id: backend.user_id,
        name: backend.nickname || backend.account || account,
        account: backend.account || account,
        role: backend.job_title || backend.role || '',
        otherRole: backend.other_role || '',
        platforms: backend.platforms || [],
        assignedStoreIds: backend.shop_scope || [],
        ...mapBackendSession(backend),
      },
    }
  }

  const { ensureDefaultUser } = await import('./authLocal')
  const { fetchLocalEmployees } = await import('./employeesLocal')
  ensureDefaultUser()
  const acc = String(account || '').trim().toLowerCase()
  const pwd = String(password || '')
  const employees = fetchLocalEmployees().data || []
  const employee = employees.find(
    (e) => e.account.toLowerCase() === acc && e.password === pwd && e.status !== false,
  )
  if (!employee) {
    throw new Error('员工账号或密码错误，请联系管理员在运营绑定中添加')
  }

  clearAccessToken()
  return {
    success: true,
    data: {
      id: employee.id,
      name: employee.name,
      account: employee.account,
      role: employee.role,
      otherRole: employee.otherRole || '',
      platforms: employee.platforms,
      assignedStoreIds: employee.assignedStoreIds || [],
      menuCodes: employee.menuCodes || [],
      backendLinked: false,
      backendUserId: null,
      backendRole: '',
      tenant_id: null,
      menus: [],
      shop_scope: [],
    },
  }
}

export async function loginWarehouse({ account, password }) {
  if (isTemuBackendEnabled()) {
    const backend = await requireBackendLogin(account, password, 'warehouse')
    return {
      success: true,
      data: {
        id: String(backend.user_id),
        name: backend.nickname || backend.account || account,
        account: backend.account || account,
        role: backend.job_title || '仓库管理员',
        phone: '',
        backendLinked: true,
        backendUserId: backend.user_id,
        backendRole: backend.role,
        tenant_id: backend.tenant_id,
        menus: backend.menus || [],
        warehouse_scope: backend.warehouse_scope || [],
        warehouse_scope_names: backend.warehouse_scope_names
          || resolveWarehouseNames(backend.warehouse_scope || []),
      },
    }
  }

  const { loginLocalWarehouse } = await import('./warehouseAuthLocal')
  const result = loginLocalWarehouse({ account, password })
  if (result.error) throw new Error(result.error)
  clearAccessToken()
  const warehouseIds = result.data.warehouseIds || []
  return {
    success: true,
    data: {
      ...result.data,
      backendLinked: false,
      menus: [],
      warehouse_scope: warehouseIds,
      warehouse_scope_names: resolveWarehouseNames(warehouseIds),
    },
  }
}
