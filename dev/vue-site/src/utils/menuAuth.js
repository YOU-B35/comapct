import {
  Briefcase,
  Box,
  CircleCheck,
  DataAnalysis,
  DocumentChecked,
  Goods,
  House,
  Key,
  Link,
  Sell,
  Setting,
  Shop,
  ShoppingBag,
  ShoppingCart,
  Switch,
  Tickets,
  TrendCharts,
  UserFilled,
  Van,
  VideoCamera,
  VideoPlay,
} from '@element-plus/icons-vue'
import { isTemuBackendEnabled } from '@/api/config'
import { SYS_MENU_SNAPSHOT } from '@/constants/menusSnapshot'

const MENU_ICONS = {
  'boss.settings': Setting,
  'boss.employees': UserFilled,
  'boss.warehouse_sites': House,
  'boss.warehouse_staff': Box,
  'boss.features': Switch,
  'boss.dashboard': TrendCharts,
  'boss.tasks': Tickets,
  'boss.accounts': Key,
  'boss.warehouse': Box,
  'employee.warehouse': Box,
  'warehouse.pending_review': DocumentChecked,
  'warehouse.pending_shipment': Van,
  'warehouse.shipped': CircleCheck,
  'warehouse.tasks': Briefcase,
  'warehouse.dashboard': TrendCharts,
  'employee.dashboard': TrendCharts,
  'employee.tasks': Briefcase,
  'employee.ai': DataAnalysis,
}

const PLATFORM_ICONS = {
  temu: Shop,
  aliexpress: Goods,
  amazon: Sell,
  walmart: ShoppingBag,
  pdd: ShoppingCart,
  douyin: VideoCamera,
  channels: VideoPlay,
  '1688': ShoppingCart,
  dtc: Link,
  shopify: Link,
  wordpress: Link,
}

export function iconForMenu(menu) {
  if (MENU_ICONS[menu.code]) return MENU_ICONS[menu.code]
  if (menu.platform && PLATFORM_ICONS[menu.platform]) return PLATFORM_ICONS[menu.platform]
  return Shop
}

export function decorateMenus(menus = []) {
  return (Array.isArray(menus) ? menus : [])
    // 本机同步助手已改为独立 .exe，不对运营前端展示
    .filter((menu) => menu?.code !== 'boss.agent_nodes' && menu?.path !== '/boss/agent-nodes')
    .map((menu) => ({
      ...menu,
      index: menu.path && menu.path !== '#' ? menu.path : menu.code,
      icon: iconForMenu(menu),
    }))
}

function sortMenus(a, b) {
  return (a.sort_order ?? 0) - (b.sort_order ?? 0)
}

export function buildSidebarTree(flatMenus = []) {
  const items = decorateMenus(flatMenus).sort(sortMenus)
  const byCode = new Map(items.map((menu) => [menu.code, { ...menu, children: [] }]))
  const roots = []

  for (const menu of items) {
    const node = byCode.get(menu.code)
    const parentCode = menu.parent_code || menu.parentCode
    if (parentCode && byCode.has(parentCode)) {
      byCode.get(parentCode).children.push(node)
    } else {
      roots.push(node)
    }
  }

  for (const node of byCode.values()) {
    node.children.sort(sortMenus)
  }

  return roots.sort(sortMenus)
}

export function flattenMenuPaths(menus = []) {
  const paths = []
  for (const menu of menus) {
    if (menu.path && menu.path !== '#') paths.push(menu.path)
    if (menu.children?.length) paths.push(...flattenMenuPaths(menu.children))
  }
  return paths
}

function flattenMenuCodes(menus = []) {
  const codes = []
  for (const menu of menus) {
    if (menu.code) codes.push(menu.code)
    if (menu.children?.length) codes.push(...flattenMenuCodes(menu.children))
  }
  return codes
}

function resolvePortal(auth) {
  if (auth.isBoss) return 'boss'
  if (auth.isWarehouse) return 'warehouse'
  return 'employee'
}

function employeePlatformList(auth) {
  return auth.backendLinked
    ? (auth.platforms || [])
    : (auth.employee?.platforms || [])
}

function allowEmployeeMenuByPlatform(menu, platforms) {
  const platform = menu.platform
  if (!platform) return false
  const list = platforms.map((p) => String(p).toLowerCase())
  if (platform === 'dtc') {
    return list.some((p) => p === 'dtc' || p === 'shopify' || p === 'wordpress')
  }
  return list.includes(String(platform).toLowerCase())
}

function allowEmployeeMenu(menu, auth) {
  const menuType = menu.menu_type
  if (menuType === 'base') return true
  if (menuType === 'admin' || menuType === 'group') return false
  if (menu.code === 'employee.warehouse') {
    const codes = auth.employee?.menuCodes || []
    return codes.includes('employee.warehouse')
  }
  if (menuType === 'module') {
    return allowEmployeeMenuByPlatform(menu, employeePlatformList(auth))
  }
  return false
}

function demoEnabledFeatureCodes() {
  return new Set(SYS_MENU_SNAPSHOT.map((item) => item.code))
}

function filterDemoMenus(auth) {
  const portal = resolvePortal(auth)
  const enabled = demoEnabledFeatureCodes()
  const portalMenus = SYS_MENU_SNAPSHOT.filter(
    (menu) => menu.portal === portal && enabled.has(menu.code),
  )

  if (portal === 'employee') {
    return portalMenus.filter((menu) => allowEmployeeMenu(menu, auth))
  }
  return portalMenus
}

export function settingsMenuOpenKeys(path = '') {
  if (
    path.startsWith('/boss/employees')
    || path.startsWith('/boss/accounts')
    || path.startsWith('/boss/features')
    || path.startsWith('/boss/warehouse-staff')
    || path.startsWith('/boss/warehouse-sites')
  ) {
    return ['boss.settings']
  }
  return []
}

export function fallbackSidebarMenus(auth) {
  return buildSidebarTree(filterDemoMenus(auth))
}

export function resolveSidebarMenus(auth) {
  if (isTemuBackendEnabled() || auth.backendLinked) {
    return buildSidebarTree(auth.menus || [])
  }
  return fallbackSidebarMenus(auth)
}

function routeAllowedByMenus(auth, menuCode) {
  const tree = resolveSidebarMenus(auth)
  const codes = new Set(flattenMenuCodes(tree))
  return codes.has(menuCode)
}

export function canAccessRoute(auth, to) {
  const record = [...to.matched].reverse().find((item) => item.meta?.menuCode)
  if (!record?.meta?.menuCode) return true

  const requiredRole = to.matched.find((item) => item.meta.role)?.meta.role
  if (requiredRole && requiredRole !== auth.role) return false

  if (isTemuBackendEnabled() || auth.backendLinked) {
    return auth.hasMenuCode(record.meta.menuCode)
  }

  return routeAllowedByMenus(auth, record.meta.menuCode)
}

export function defaultLandingPath(auth) {
  const first = auth.menuPaths[0]
  if (first) return first
  return auth.isBoss ? '/boss/dashboard' : auth.isWarehouse ? '/warehouse/pending-review' : '/employee/dashboard'
}
