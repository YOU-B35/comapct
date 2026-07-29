/**
 * 与 backend TenantSchemaMigration.seedMenus 保持同步。
 * Demo 模式侧栏与路由守卫的单源菜单目录。
 */
export const SYS_MENU_SNAPSHOT = [
  { code: 'boss.dashboard', parent_code: null, portal: 'boss', platform: null, path: '/boss/dashboard', label: '运营总览', menu_type: 'admin', sort_order: 10 },
  { code: 'boss.tasks', parent_code: null, portal: 'boss', platform: null, path: '/boss/tasks', label: '任务分配', menu_type: 'admin', sort_order: 20 },
  { code: 'boss.warehouse', parent_code: null, portal: 'boss', platform: null, path: '/boss/warehouse-orders', label: '仓库下单', menu_type: 'admin', sort_order: 25 },
  { code: 'boss.platform.temu', parent_code: null, portal: 'boss', platform: 'temu', path: '/boss/temu', label: 'Temu 运营', menu_type: 'module', sort_order: 30 },
  { code: 'boss.platform.aliexpress', parent_code: null, portal: 'boss', platform: 'aliexpress', path: '/boss/aliexpress', label: 'AliExpress 运营', menu_type: 'module', sort_order: 40 },
  { code: 'boss.platform.amazon', parent_code: null, portal: 'boss', platform: 'amazon', path: '/boss/amazon', label: 'Amazon 运营', menu_type: 'module', sort_order: 50 },
  { code: 'boss.platform.walmart', parent_code: null, portal: 'boss', platform: 'walmart', path: '/boss/walmart', label: 'Walmart 运营', menu_type: 'module', sort_order: 60 },
  { code: 'boss.platform.pdd', parent_code: null, portal: 'boss', platform: 'pdd', path: '/boss/pdd', label: '拼多多运营', menu_type: 'module', sort_order: 70 },
  { code: 'boss.platform.douyin', parent_code: null, portal: 'boss', platform: 'douyin', path: '/boss/douyin', label: '抖音运营', menu_type: 'module', sort_order: 80 },
  { code: 'boss.platform.channels', parent_code: null, portal: 'boss', platform: 'channels', path: '/boss/channels', label: '视频号运营', menu_type: 'module', sort_order: 90 },
  { code: 'boss.platform.1688', parent_code: null, portal: 'boss', platform: '1688', path: '/boss/1688', label: '1688 运营', menu_type: 'module', sort_order: 100 },
  { code: 'boss.platform.dtc', parent_code: null, portal: 'boss', platform: 'dtc', path: '/boss/dtc', label: '独立站运营', menu_type: 'module', sort_order: 110 },
  { code: 'boss.settings', parent_code: null, portal: 'boss', platform: null, path: '#', label: '设置', menu_type: 'group', sort_order: 120 },
  { code: 'boss.employees', parent_code: 'boss.settings', portal: 'boss', platform: null, path: '/boss/employees', label: '运营绑定', menu_type: 'admin', sort_order: 121 },
  { code: 'boss.warehouse_sites', parent_code: 'boss.settings', portal: 'boss', platform: null, path: '/boss/warehouse-sites', label: '仓库设置', menu_type: 'admin', sort_order: 122 },
  { code: 'boss.warehouse_staff', parent_code: 'boss.settings', portal: 'boss', platform: null, path: '/boss/warehouse-staff', label: '仓库人员', menu_type: 'admin', sort_order: 123 },
  { code: 'boss.accounts', parent_code: 'boss.settings', portal: 'boss', platform: null, path: '/boss/accounts', label: '账户绑定', menu_type: 'admin', sort_order: 125 },
  { code: 'boss.features', parent_code: 'boss.settings', portal: 'boss', platform: null, path: '/boss/features', label: '功能开关', menu_type: 'admin', sort_order: 126 },

  { code: 'employee.dashboard', parent_code: null, portal: 'employee', platform: null, path: '/employee/dashboard', label: '我的工作台', menu_type: 'base', sort_order: 10 },
  { code: 'employee.warehouse', parent_code: null, portal: 'employee', platform: null, path: '/employee/warehouse-orders', label: '仓库下单', menu_type: 'module', sort_order: 85 },
  { code: 'employee.tasks', parent_code: null, portal: 'employee', platform: null, path: '/employee/tasks', label: '任务中心', menu_type: 'base', sort_order: 90 },
  { code: 'employee.ai', parent_code: null, portal: 'employee', platform: null, path: '/employee/ai', label: 'AI 办公', menu_type: 'base', sort_order: 100 },
  { code: 'employee.platform.temu', parent_code: null, portal: 'employee', platform: 'temu', path: '/employee/temu', label: 'Temu 运营', menu_type: 'module', sort_order: 20 },
  { code: 'employee.platform.aliexpress', parent_code: null, portal: 'employee', platform: 'aliexpress', path: '/employee/aliexpress', label: 'AliExpress 运营', menu_type: 'module', sort_order: 30 },
  { code: 'employee.platform.amazon', parent_code: null, portal: 'employee', platform: 'amazon', path: '/employee/amazon', label: 'Amazon 运营', menu_type: 'module', sort_order: 40 },
  { code: 'employee.platform.walmart', parent_code: null, portal: 'employee', platform: 'walmart', path: '/employee/walmart', label: 'Walmart 运营', menu_type: 'module', sort_order: 50 },
  { code: 'employee.platform.pdd', parent_code: null, portal: 'employee', platform: 'pdd', path: '/employee/pdd', label: '拼多多运营', menu_type: 'module', sort_order: 60 },
  { code: 'employee.platform.douyin', parent_code: null, portal: 'employee', platform: 'douyin', path: '/employee/douyin', label: '抖音运营', menu_type: 'module', sort_order: 70 },
  { code: 'employee.platform.channels', parent_code: null, portal: 'employee', platform: 'channels', path: '/employee/channels', label: '视频号运营', menu_type: 'module', sort_order: 80 },
  { code: 'employee.platform.1688', parent_code: null, portal: 'employee', platform: '1688', path: '/employee/1688', label: '1688 运营', menu_type: 'module', sort_order: 85 },
  { code: 'employee.platform.dtc', parent_code: null, portal: 'employee', platform: 'dtc', path: '/employee/dtc', label: '独立站运营', menu_type: 'module', sort_order: 88 },

  { code: 'warehouse.pending_review', parent_code: null, portal: 'warehouse', platform: null, path: '/warehouse/pending-review', label: '待审核', menu_type: 'base', sort_order: 10 },
  { code: 'warehouse.pending_shipment', parent_code: null, portal: 'warehouse', platform: null, path: '/warehouse/pending-shipment', label: '待发货', menu_type: 'base', sort_order: 20 },
  { code: 'warehouse.shipped', parent_code: null, portal: 'warehouse', platform: null, path: '/warehouse/shipped', label: '已发货', menu_type: 'base', sort_order: 30 },
  { code: 'warehouse.tasks', parent_code: null, portal: 'warehouse', platform: null, path: '/warehouse/tasks', label: '任务中心', menu_type: 'base', sort_order: 40 },
]
