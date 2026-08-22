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
  PictureFilled,
  Sell,
  Setting,
  Shop,
  ShoppingBag,
  ShoppingCart,
  Upload,
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
  'boss.ai_image': PictureFilled,
  'boss.sau': VideoCamera,
  'boss.auto_upload': Upload,
  'boss.tasks': Tickets,
  'boss.accounts': Key,
  'boss.warehouse': Box,
  'boss.nav.platforms': Shop,
  'boss.nav.tools': DataAnalysis,
  'employee.warehouse': Box,
  'employee.nav.platforms': Shop,
  'employee.nav.tools': DataAnalysis,
  'warehouse.pending_review': DocumentChecked,
  'warehouse.pending_shipment': Van,
  'warehouse.shipped': CircleCheck,
  'warehouse.tasks': Briefcase,
  'warehouse.dashboard': TrendCharts,
  'employee.dashboard': TrendCharts,
  'employee.tasks': Briefcase,
  'employee.sau': VideoCamera,
  'employee.ai': DataAnalysis,
  'employee.ai_image': PictureFilled,
  'employee.auto_upload': Upload,
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
  if (menu.code === 'employee.sau') {
    return (auth.employee?.otherRole || '') === '自媒体运营'
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

/** 侧栏展示用折叠分组（不入库，仅前端整理） */
const NAV_PLATFORM_GROUP = {
  boss: { code: 'boss.nav.platforms', label: '平台运营', sort_order: 28 },
  employee: { code: 'employee.nav.platforms', label: '平台运营', sort_order: 18 },
}

const NAV_TOOLS_GROUP = {
  boss: { code: 'boss.nav.tools', label: '智能工具', sort_order: 14 },
  employee: { code: 'employee.nav.tools', label: '智能工具', sort_order: 93 },
}

const TOOL_MENU_CODES = new Set([
  'boss.ai_image',
  'boss.sau',
  'boss.auto_upload',
  'employee.ai',
  'employee.ai_image',
  'employee.sau',
  'employee.auto_upload',
])

const PLATFORM_PATH_RE = /^\/(boss|employee)\/(temu|aliexpress|amazon|walmart|pdd|taobao|douyin|channels|1688|dtc)(\/|$)/
const TOOLS_PATH_RE = /^\/(boss|employee)\/(ai-image|ai|sau|auto-upload)(\/|$)/

function isPlatformMenu(menu) {
  return menu?.menu_type === 'module' && Boolean(menu.platform)
}

function shortenPlatformLabel(label = '') {
  return String(label).replace(/\s*运营$/u, '').trim() || label
}

function makeNavGroup(meta, portal, children) {
  const [group] = decorateMenus([
    {
      code: meta.code,
      parent_code: null,
      portal,
      platform: null,
      path: '#',
      label: meta.label,
      menu_type: 'group',
      sort_order: meta.sort_order,
    },
  ])
  group.children = children
  return group
}

/**
 * 把平台 / 智能工具收成折叠组，避免侧栏一眼全展开显得杂乱。
 * 仅影响展示树；叶子菜单 code/path 不变。
 */
export function organizeSidebarGroups(tree = []) {
  if (!Array.isArray(tree) || !tree.length) return tree

  const portalFromNode = tree.find((m) => m.portal)?.portal
  const resolvedPortal = portalFromNode || 'boss'
  if (resolvedPortal === 'warehouse') return tree

  const platforms = []
  const tools = []
  const rest = []

  for (const item of tree) {
    if (item?.children?.length && (item.menu_type === 'group' || String(item.code || '').endsWith('.settings'))) {
      rest.push(item)
      continue
    }
    if (isPlatformMenu(item)) {
      platforms.push({
        ...item,
        label: shortenPlatformLabel(item.label),
      })
      continue
    }
    if (TOOL_MENU_CODES.has(item.code)) {
      tools.push(item)
      continue
    }
    rest.push(item)
  }

  const out = [...rest]
  if (platforms.length) {
    const meta = NAV_PLATFORM_GROUP[resolvedPortal] || NAV_PLATFORM_GROUP.boss
    out.push(makeNavGroup(meta, resolvedPortal, platforms.sort(sortMenus)))
  }
  if (tools.length) {
    const meta = NAV_TOOLS_GROUP[resolvedPortal] || NAV_TOOLS_GROUP.boss
    out.push(makeNavGroup(meta, resolvedPortal, tools.sort(sortMenus)))
  }
  return out.sort(sortMenus)
}

/** @deprecated 使用 sidebarMenuOpenKeys */
export function settingsMenuOpenKeys(path = '') {
  return sidebarMenuOpenKeys(path)
}

/** 仅展开当前路由所在分组，其它默认收起 */
export function sidebarMenuOpenKeys(path = '') {
  const keys = []
  if (
    path.startsWith('/boss/employees')
    || path.startsWith('/boss/accounts')
    || path.startsWith('/boss/features')
    || path.startsWith('/boss/warehouse-staff')
    || path.startsWith('/boss/warehouse-sites')
    || path.startsWith('/boss/ops-teams')
  ) {
    keys.push('boss.settings')
  }
  const platformMatch = String(path || '').match(PLATFORM_PATH_RE)
  if (platformMatch) {
    keys.push(`${platformMatch[1]}.nav.platforms`)
  }
  const toolsMatch = String(path || '').match(TOOLS_PATH_RE)
  if (toolsMatch) {
    keys.push(`${toolsMatch[1]}.nav.tools`)
  }
  return keys
}

export function fallbackSidebarMenus(auth) {
  return buildSidebarTree(filterDemoMenus(auth))
}

const EMPLOYEE_AI_IMAGE_MENU = {
  code: 'employee.ai_image',
  parent_code: null,
  portal: 'employee',
  platform: null,
  path: '/employee/ai-image',
  label: 'AI 生图',
  menu_type: 'base',
  sort_order: 101,
}

const BOSS_AI_IMAGE_MENU = {
  code: 'boss.ai_image',
  parent_code: null,
  portal: 'boss',
  platform: null,
  path: '/boss/ai-image',
  label: 'AI 生图',
  menu_type: 'base',
  sort_order: 15,
}

const BOSS_SAU_MENU = {
  code: 'boss.sau',
  parent_code: null,
  portal: 'boss',
  platform: null,
  path: '/boss/sau',
  label: '自媒体运营',
  menu_type: 'admin',
  sort_order: 18,
}

/** 后端菜单未下发时，仍注入「AI 生图」（前端能力，接口走线上 playground） */
function ensureAiImageMenu(tree = [], portal) {
  const menu = portal === 'boss' ? BOSS_AI_IMAGE_MENU : EMPLOYEE_AI_IMAGE_MENU
  const codes = new Set(flattenMenuCodes(tree))
  if (codes.has(menu.code)) return tree
  const [decorated] = decorateMenus([menu])
  return [...tree, decorated].sort(sortMenus)
}

/** Boss 端注入「自媒体运营」（即使后端尚未下发菜单） */
function ensureBossSauMenu(tree = []) {
  const codes = new Set(flattenMenuCodes(tree))
  if (codes.has(BOSS_SAU_MENU.code)) return tree
  const [decorated] = decorateMenus([BOSS_SAU_MENU])
  return [...tree, decorated].sort(sortMenus)
}

const BOSS_AUTO_UPLOAD_MENU = {
  code: 'boss.auto_upload',
  parent_code: null,
  portal: 'boss',
  platform: null,
  path: '/boss/auto-upload',
  label: '自动上货',
  menu_type: 'admin',
  sort_order: 19,
}

const EMPLOYEE_AUTO_UPLOAD_MENU = {
  code: 'employee.auto_upload',
  parent_code: null,
  portal: 'employee',
  platform: null,
  path: '/employee/auto-upload',
  label: '自动上货',
  menu_type: 'base',
  sort_order: 96,
}

function ensureCommanderAutoUploadMenu(tree = [], portal) {
  const menu = portal === 'boss' ? BOSS_AUTO_UPLOAD_MENU : EMPLOYEE_AUTO_UPLOAD_MENU
  const codes = new Set(flattenMenuCodes(tree))
  if (codes.has(menu.code)) return tree
  const [decorated] = decorateMenus([menu])
  return [...tree, decorated].sort(sortMenus)
}

export function resolveSidebarMenus(auth) {
  let tree
  if (isTemuBackendEnabled() || auth.backendLinked) {
    tree = buildSidebarTree(auth.menus || [])
  } else {
    tree = fallbackSidebarMenus(auth)
  }
  const portal = resolvePortal(auth)
  if (portal === 'employee' || portal === 'boss') {
    tree = ensureAiImageMenu(tree, portal)
    tree = ensureCommanderAutoUploadMenu(tree, portal)
  }
  if (portal === 'boss') {
    tree = ensureBossSauMenu(tree)
  }
  return organizeSidebarGroups(tree)
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

  // AI 生图 / Boss 自媒体为前端注入能力，不依赖后端菜单下发
  if (record.meta.menuCode === 'employee.ai_image' && auth.role === 'employee') {
    return true
  }
  if (record.meta.menuCode === 'boss.ai_image' && auth.role === 'boss') {
    return true
  }
  if (record.meta.menuCode === 'boss.sau' && auth.role === 'boss') {
    return true
  }
  if (record.meta.menuCode === 'boss.auto_upload' && auth.role === 'boss') {
    return true
  }
  if (record.meta.menuCode === 'employee.auto_upload' && auth.role === 'employee') {
    return true
  }

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
