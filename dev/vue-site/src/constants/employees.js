/** 运营绑定 Demo 样本 */
import {
  DTC_PLATFORM_OPTIONS,
  DOMESTIC_PLATFORM_OPTIONS,
  MARKETPLACE_PLATFORM_OPTIONS,
  OTHER_PLATFORM_OPTIONS,
  PLATFORM_OPTION_GROUPS,
  platformDisplayLabels,
} from './platforms'

export { PLATFORM_OPTION_GROUPS }

/** 员工端仓库下单菜单 code，与后端 sys_menu / menu_codes 一致 */
export const WAREHOUSE_MENU_CODE = 'employee.warehouse'

/** 员工端自媒体运营菜单 code */
export const SAU_MENU_CODE = 'employee.sau'

/** 运营绑定「其他角色」单选（非必填） */
export const OTHER_ROLE_OPTIONS = ['自媒体运营', '其他']

export const DEMO_EMPLOYEES = [
  {
    id: 'demo_emp_1',
    name: '王一鸣',
    account: 'wangyiming@yituo-outdoor.com',
    password: 'Emp@Demo123',
    role: 'Temu 运营',
    platforms: ['temu'],
    assignedStoreIds: ['demo_temu_1', 'demo_temu_2'],
    phone: '13800138001',
    status: true,
    boundAt: '2026-06-20 09:15:00',
  },
  {
    id: 'demo_emp_2',
    name: '李婷',
    account: 'liting@yituo-outdoor.com',
    password: 'Emp@Demo456',
    role: 'Temu 运营',
    platforms: ['temu'],
    assignedStoreIds: [],
    phone: '13800138002',
    status: true,
    boundAt: '2026-06-21 10:30:00',
  },
  {
    id: 'demo_emp_3',
    name: '张强',
    account: 'zhangqiang@yituo-outdoor.com',
    password: 'Emp@Demo789',
    role: 'AliExpress 运营',
    platforms: ['aliexpress'],
    assignedStoreIds: ['demo_aliexpress_1', 'demo_aliexpress_2'],
    phone: '13800138003',
    status: true,
    boundAt: '2026-06-22 14:20:00',
  },
  {
    id: 'demo_emp_4',
    name: '陈敏',
    account: 'chenmin@yituo-outdoor.com',
    password: 'Emp@Demo321',
    role: '独立站运营',
    platforms: ['dtc'],
    assignedStoreIds: ['demo_shopify_1', 'demo_shopify_2', 'demo_wordpress_1'],
    phone: '13800138004',
    status: true,
    boundAt: '2026-06-23 11:00:00',
  },
  {
    id: 'demo_emp_5',
    name: '赵磊',
    account: 'zhaolei@yituo-outdoor.com',
    password: 'Emp@Demo654',
    role: '1688 采购',
    platforms: ['1688'],
    assignedStoreIds: ['demo_1688_1', 'demo_1688_2'],
    phone: '13800138005',
    status: true,
    boundAt: '2026-06-24 08:30:00',
  },
  {
    id: 'demo_emp_6',
    name: '刘洋',
    account: 'liuyang@yituo-outdoor.com',
    password: 'Emp@Demo987',
    role: 'Amazon 运营',
    platforms: ['amazon'],
    assignedStoreIds: ['demo_amazon_1', 'demo_amazon_2'],
    phone: '13800138006',
    status: true,
    boundAt: '2026-06-24 10:00:00',
  },
  {
    id: 'demo_emp_7',
    name: '周婷',
    account: 'zhouting@yituo-outdoor.com',
    password: 'Emp@Demo852',
    role: 'Walmart 运营',
    platforms: ['walmart'],
    assignedStoreIds: ['demo_walmart_1', 'demo_walmart_2'],
    phone: '13800138007',
    status: true,
    boundAt: '2026-06-24 14:00:00',
  },
  {
    id: 'demo_emp_8',
    name: '孙浩',
    account: 'sunhao@yituo-outdoor.com',
    password: 'Emp@Demo741',
    role: '拼多多运营',
    platforms: ['pdd'],
    assignedStoreIds: ['demo_pdd_1', 'demo_pdd_2'],
    phone: '13800138008',
    status: true,
    boundAt: '2026-06-24 19:00:00',
  },
  {
    id: 'demo_emp_9',
    name: '林雪',
    account: 'linxue@yituo-outdoor.com',
    password: 'Emp@Demo963',
    role: '抖音运营',
    platforms: ['douyin'],
    assignedStoreIds: ['demo_douyin_1', 'demo_douyin_2'],
    phone: '13800138009',
    status: true,
    boundAt: '2026-06-24 20:00:00',
  },
  {
    id: 'demo_emp_10',
    name: '何静',
    account: 'hejing@yituo-outdoor.com',
    password: 'Emp@Demo159',
    role: '视频号运营',
    platforms: ['channels'],
    assignedStoreIds: ['demo_channels_1', 'demo_channels_2'],
    phone: '13800138010',
    status: true,
    boundAt: '2026-06-24 21:00:00',
  },
]

export const PLATFORM_OPTIONS = [
  ...MARKETPLACE_PLATFORM_OPTIONS,
  ...DOMESTIC_PLATFORM_OPTIONS,
  ...DTC_PLATFORM_OPTIONS,
  ...OTHER_PLATFORM_OPTIONS,
]

export function platformLabels(platforms) {
  const map = Object.fromEntries(PLATFORM_OPTIONS.map((p) => [p.value, p.label]))
  return platformDisplayLabels(platforms, map).join('、') || '—'
}

export const ROLE_OPTIONS = [
  'Temu 运营',
  'AliExpress 运营',
  '1688 采购',
  '独立站运营',
  'Amazon 运营',
  'Walmart 运营',
  '拼多多运营',
  '抖音运营',
  '视频号运营',
]
