import { setLocalTenantId } from '@/utils/tenantStorage'
import { fetchLocalEmployees, saveLocalEmployee } from './employeesLocal'

const STORAGE_KEY = 'crosshub_auth_users'

const DEFAULT_USER = {
  id: 'demo_company_1',
  company: '泰州亿拓户外用品有限公司',
  account: 'admin@crosshub.cn',
  password: '12345678',
  createdAt: '2026-06-18 09:00:00',
}

function loadAll() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveAll(users) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(users))
}

function createId() {
  return `user_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

function nextLocalTenantId() {
  const key = 'crosshub_local_tenant_seq'
  const next = Number(localStorage.getItem(key) || 1000) + 1
  localStorage.setItem(key, String(next))
  return next
}

/** 确保默认演示账号存在 */
export function ensureDefaultUser() {
  const users = loadAll()
  if (users.some((u) => u.account === DEFAULT_USER.account)) return
  saveAll([{ ...DEFAULT_USER, tenant_id: 1 }, ...users])
}

export function findUserByAccount(account) {
  ensureDefaultUser()
  const acc = String(account || '').trim().toLowerCase()
  return loadAll().find((u) => u.account.toLowerCase() === acc) || null
}

export function registerLocalUser({ company, account, password }) {
  ensureDefaultUser()

  const companyName = String(company || '').trim()
  const acc = String(account || '').trim()
  const pwd = String(password || '')

  if (!companyName) return { error: '请填写企业名称' }
  if (!acc) return { error: '请填写登录账号' }
  if (pwd.length < 6) return { error: '密码至少 6 位' }

  const users = loadAll()
  if (users.some((u) => u.account.toLowerCase() === acc.toLowerCase())) {
    return { error: '该账号已注册，请直接登录' }
  }

  const tenantId = nextLocalTenantId()
  const user = {
    id: createId(),
    tenant_id: tenantId,
    company: companyName,
    account: acc,
    password: pwd,
    createdAt: new Date().toISOString().replace('T', ' ').slice(0, 19),
  }
  users.push(user)
  saveAll(users)
  setLocalTenantId(tenantId)
  return { success: true, data: { ...user, password: undefined, tenant_code: `local-${tenantId}` } }
}

/** 离线模式：员工加入已有本地企业（按企业名匹配 Boss），并写入 employees 列表 */
export function registerLocalEmployee({ company, tenantCode, account, password, name }) {
  ensureDefaultUser()
  const companyName = String(company || '').trim()
  const code = String(tenantCode || '').trim()
  const acc = String(account || '').trim()
  const pwd = String(password || '')
  const displayName = String(name || '').trim() || acc

  if (!companyName && !code) return { error: '请填写企业名称或企业邀请码' }
  if (!acc) return { error: '请填写登录账号' }
  if (pwd.length < 6) return { error: '密码至少 6 位' }

  const users = loadAll()
  let boss = null
  if (code.startsWith('local-')) {
    const tid = Number(code.slice('local-'.length))
    boss = users.find((u) => Number(u.tenant_id) === tid) || null
  }
  if (!boss && companyName) {
    boss = users.find((u) => String(u.company || '').toLowerCase() === companyName.toLowerCase()) || null
  }
  if (!boss) {
    return { error: '未找到该企业，请确认企业名称或邀请码' }
  }

  const existing = fetchLocalEmployees().data || []
  if (existing.some((e) => String(e.account).toLowerCase() === acc.toLowerCase())) {
    return { error: '该账号已注册，请直接登录' }
  }
  if (users.some((u) => u.account.toLowerCase() === acc.toLowerCase())) {
    return { error: '该账号已注册，请直接登录' }
  }

  setLocalTenantId(boss.tenant_id)
  const saved = saveLocalEmployee({
    name: displayName,
    account: acc,
    role: '运营',
    platforms: ['temu'],
    password: pwd,
    status: true,
    assignedStoreIds: [],
    menuCodes: [],
  })
  if (saved.error) return saved
  return {
    success: true,
    data: {
      tenant_id: boss.tenant_id,
      tenant_code: code || `local-${boss.tenant_id}`,
      company: boss.company,
      account: acc,
      name: displayName,
      portal_role: 'employee',
    },
  }
}

export function loginLocalBoss({ account, password }) {
  const user = findUserByAccount(account)
  if (!user) return { error: '账号不存在，请先注册' }
  if (user.password !== password) return { error: '密码错误' }
  if (user.tenant_id) setLocalTenantId(user.tenant_id)
  return {
    success: true,
    data: {
      id: user.id,
      tenant_id: user.tenant_id || null,
      company: user.company,
      account: user.account,
    },
  }
}
