import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { formatMoneyDecimal } from '@/utils/format'
import { dateOffset } from '@/utils/date'

function product({
  id,
  name,
  category,
  price,
  dailySales,
  salesHistory,
  listedDaysAgo,
  url,
  totalSales,
}) {
  const history = salesHistory || Array(7).fill(dailySales)
  return {
    productId: id,
    name,
    category,
    price,
    priceText: formatMoneyDecimal(price),
    dailySales,
    totalSales: totalSales ?? dailySales * 90,
    salesHistory: history,
    listedAt: dateOffset(listedDaysAgo),
    url,
  }
}

/** Demo 竞店列表 */
export const DEMO_COMPETITORS = [
  {
    id: 'demo_comp_matsumoto',
    label: '松本户外专营店',
    url: 'https://www.temu.com/mall.html?mall_id=demo_matsumoto_outdoor',
    createdAt: '2026-06-18 09:00:00',
    updatedAt: '2026-06-24 08:00:00',
    lastAnalyzedAt: null,
  },
  {
    id: 'demo_comp_shanye',
    label: '山野装备旗舰店',
    url: 'https://www.temu.com/mall.html?mall_id=demo_shanye_gear',
    createdAt: '2026-06-20 10:30:00',
    updatedAt: '2026-06-24 08:00:00',
    lastAnalyzedAt: null,
  },
]

const MATSUMOTO_BASE = [
  product({ id: 'MT-001', name: '全自动充气帐篷 3-4人', category: '帐篷', price: 189.9, dailySales: 42, listedDaysAgo: 28, url: 'https://www.temu.com/goods/demo_mt001', salesHistory: [38, 40, 41, 39, 43, 44, 42], totalSales: 3680 }),
  product({ id: 'MT-002', name: '户外折叠桌椅套装', category: '露营炊具', price: 129.0, dailySales: 35, listedDaysAgo: 25, url: 'https://www.temu.com/goods/demo_mt002', salesHistory: [32, 34, 33, 36, 35, 34, 35], totalSales: 2900 }),
  product({ id: 'MT-003', name: '碳纤维登山杖一对', category: '登山杖', price: 59.9, dailySales: 58, listedDaysAgo: 32, url: 'https://www.temu.com/goods/demo_mt003', salesHistory: [52, 55, 54, 56, 57, 58, 58], totalSales: 5120 }),
  product({ id: 'MT-004', name: 'USB 充电头灯', category: '户外照明', price: 39.9, dailySales: 52, listedDaysAgo: 20, url: 'https://www.temu.com/goods/demo_mt004', salesHistory: [48, 50, 49, 51, 52, 53, 52], totalSales: 4200 }),
  product({ id: 'MT-005', name: '防水冲锋衣男款', category: '户外服饰', price: 149.0, dailySales: 31, listedDaysAgo: 18, url: 'https://www.temu.com/goods/demo_mt005', salesHistory: [28, 29, 30, 31, 32, 30, 31], totalSales: 2650 }),
  product({ id: 'MT-006', name: '露营睡袋零下 10 度', category: '睡袋', price: 99.0, dailySales: 26, listedDaysAgo: 22, url: 'https://www.temu.com/goods/demo_mt006', salesHistory: [24, 25, 26, 25, 27, 26, 26], totalSales: 2100 }),
  product({ id: 'MT-007', name: '户外野餐炉具套装', category: '露营炊具', price: 79.0, dailySales: 39, listedDaysAgo: 15, url: 'https://www.temu.com/goods/demo_mt007', salesHistory: [36, 38, 37, 39, 40, 38, 39], totalSales: 3200 }),
  product({ id: 'MT-008', name: '登山背包 50L', category: '运动配件', price: 119.0, dailySales: 21, listedDaysAgo: 30, url: 'https://www.temu.com/goods/demo_mt008', salesHistory: [19, 20, 21, 20, 22, 21, 21], totalSales: 1850 }),
  product({ id: 'MT-009', name: '速开防晒天幕 3x3m', category: '帐篷', price: 89.0, dailySales: 54, listedDaysAgo: 12, url: 'https://www.temu.com/goods/demo_mt009', salesHistory: [50, 52, 53, 54, 55, 53, 54], totalSales: 4100 }),
  product({ id: 'MT-010', name: '户外保温运动水壶', category: '运动配件', price: 45.0, dailySales: 30, listedDaysAgo: 14, url: 'https://www.temu.com/goods/demo_mt010', salesHistory: [28, 29, 30, 29, 31, 30, 30], totalSales: 2400 }),
]

const MATSUMOTO_DAY5_NEW = product({
  id: 'MT-011',
  name: '折叠露营推车',
  category: '运动配件',
  price: 168.0,
  dailySales: 16,
  listedDaysAgo: 5,
  url: 'https://www.temu.com/goods/demo_mt011',
  salesHistory: [8, 10, 12, 13, 14, 15, 16],
  totalSales: 420,
})

const MATSUMOTO_DAY2_NEW = product({
  id: 'MT-012',
  name: '户外战术腰带',
  category: '户外服饰',
  price: 35.9,
  dailySales: 11,
  listedDaysAgo: 2,
  url: 'https://www.temu.com/goods/demo_mt012',
  salesHistory: [4, 6, 7, 8, 9, 10, 11],
  totalSales: 180,
})

const MATSUMOTO_TODAY_NEW = [
  product({
    id: 'MT-013',
    name: '轻量双人徒步帐篷',
    category: '帐篷',
    price: 159.0,
    dailySales: 9,
    listedDaysAgo: 0,
    url: 'https://www.temu.com/goods/demo_mt013',
    salesHistory: [0, 0, 0, 0, 0, 0, 9],
    totalSales: 9,
  }),
  product({
    id: 'MT-014',
    name: '户外防蚊露营灯串',
    category: '户外照明',
    price: 49.9,
    dailySales: 7,
    listedDaysAgo: 0,
    url: 'https://www.temu.com/goods/demo_mt014',
    salesHistory: [0, 0, 0, 0, 0, 0, 7],
    totalSales: 7,
  }),
]

function cloneProducts(list) {
  return list.map((p) => ({ ...p, salesHistory: [...p.salesHistory] }))
}

function withDailySales(list, overrides) {
  return list.map((p) => {
    const next = overrides[p.productId]
    if (!next) return { ...p, salesHistory: [...p.salesHistory] }
    const history = [...p.salesHistory.slice(1), next.dailySales]
    return { ...p, dailySales: next.dailySales, salesHistory: history, totalSales: p.totalSales + next.dailySales }
  })
}

function buildMatsumotoSnapshots() {
  const day7 = cloneProducts(MATSUMOTO_BASE)
  const day5 = [...cloneProducts(MATSUMOTO_BASE), { ...MATSUMOTO_DAY5_NEW, listedDaysAgo: 5, listedAt: dateOffset(5) }]
  const day2 = [...cloneProducts(day5), { ...MATSUMOTO_DAY2_NEW, listedDaysAgo: 2, listedAt: dateOffset(2) }]

  const yesterday = withDailySales(cloneProducts(day2), {
    'MT-003': { dailySales: 58 },
    'MT-004': { dailySales: 52 },
    'MT-009': { dailySales: 51 },
  })

  const today = [
    ...withDailySales(
      yesterday.filter((p) => !['MT-013', 'MT-014'].includes(p.productId)),
      {
        'MT-003': { dailySales: 142 },
        'MT-004': { dailySales: 118 },
        'MT-009': { dailySales: 96 },
      },
    ),
    ...MATSUMOTO_TODAY_NEW,
  ]

  return [
    { daysAgo: 7, products: day7 },
    { daysAgo: 5, products: day5 },
    { daysAgo: 2, products: day2 },
    { daysAgo: 1, products: yesterday },
    { daysAgo: 0, products: today },
  ]
}

const SHANYE_BASE = [
  product({ id: 'SY-001', name: '铝合金折叠露营桌', category: '露营炊具', price: 138.0, dailySales: 28, listedDaysAgo: 24, url: 'https://www.temu.com/goods/demo_sy001', salesHistory: [25, 26, 27, 28, 29, 28, 28], totalSales: 2200 }),
  product({ id: 'SY-002', name: '户外防晒冰袖两件套', category: '户外服饰', price: 19.9, dailySales: 95, listedDaysAgo: 16, url: 'https://www.temu.com/goods/demo_sy002', salesHistory: [88, 90, 92, 93, 94, 95, 95], totalSales: 7800 }),
  product({ id: 'SY-003', name: '便携燃气炉头', category: '露营炊具', price: 68.0, dailySales: 44, listedDaysAgo: 19, url: 'https://www.temu.com/goods/demo_sy003', salesHistory: [40, 42, 43, 44, 45, 44, 44], totalSales: 3600 }),
  product({ id: 'SY-004', name: '专业攀岩护膝', category: '运动配件', price: 55.0, dailySales: 19, listedDaysAgo: 26, url: 'https://www.temu.com/goods/demo_sy004', salesHistory: [17, 18, 19, 18, 20, 19, 19], totalSales: 1500 }),
  product({ id: 'SY-005', name: '户外急救医疗包', category: '运动配件', price: 42.0, dailySales: 33, listedDaysAgo: 11, url: 'https://www.temu.com/goods/demo_sy005', salesHistory: [30, 31, 32, 33, 34, 33, 33], totalSales: 2800 }),
  product({ id: 'SY-006', name: '双人防潮充气垫', category: '睡袋', price: 109.0, dailySales: 24, listedDaysAgo: 21, url: 'https://www.temu.com/goods/demo_sy006', salesHistory: [22, 23, 24, 23, 25, 24, 24], totalSales: 1950 }),
  product({ id: 'SY-007', name: '太阳能露营马灯', category: '户外照明', price: 76.0, dailySales: 37, listedDaysAgo: 13, url: 'https://www.temu.com/goods/demo_sy007', salesHistory: [34, 35, 36, 37, 38, 37, 37], totalSales: 3100 }),
  product({ id: 'SY-008', name: '户外速干裤男', category: '户外服饰', price: 69.9, dailySales: 41, listedDaysAgo: 17, url: 'https://www.temu.com/goods/demo_sy008', salesHistory: [38, 39, 40, 41, 42, 41, 41], totalSales: 3300 }),
]

const SHANYE_DAY3_NEW = product({
  id: 'SY-009',
  name: '露营折叠收纳箱 55L',
  category: '运动配件',
  price: 88.0,
  dailySales: 14,
  listedDaysAgo: 3,
  url: 'https://www.temu.com/goods/demo_sy009',
  salesHistory: [5, 7, 9, 10, 12, 13, 14],
  totalSales: 320,
})

const SHANYE_TODAY_NEW = product({
  id: 'SY-010',
  name: '户外防风打火机套装',
  category: '露营炊具',
  price: 29.9,
  dailySales: 6,
  listedDaysAgo: 0,
  url: 'https://www.temu.com/goods/demo_sy010',
  salesHistory: [0, 0, 0, 0, 0, 0, 6],
  totalSales: 6,
})

function buildShanyeSnapshots() {
  const day7 = cloneProducts(SHANYE_BASE)
  const day3 = [...cloneProducts(SHANYE_BASE), { ...SHANYE_DAY3_NEW, listedDaysAgo: 3, listedAt: dateOffset(3) }]

  const yesterday = withDailySales(cloneProducts(day3), {
    'SY-002': { dailySales: 95 },
    'SY-007': { dailySales: 36 },
  })

  const today = [
    ...withDailySales(cloneProducts(yesterday), {
      'SY-002': { dailySales: 186 },
      'SY-007': { dailySales: 78 },
    }),
    SHANYE_TODAY_NEW,
  ]

  return [
    { daysAgo: 7, products: day7 },
    { daysAgo: 3, products: day3 },
    { daysAgo: 1, products: yesterday },
    { daysAgo: 0, products: today },
  ]
}

const DEMO_SNAPSHOT_BUILDERS = {
  demo_comp_matsumoto: buildMatsumotoSnapshots,
  demo_comp_shanye: buildShanyeSnapshots,
}

/** 根据竞店 id 或网址识别 Demo 模板 */
export function resolveDemoTemplateId(competitor) {
  const id = competitor?.id || ''
  const url = String(competitor?.url || '')
  if (id === 'demo_comp_matsumoto' || url.includes('demo_matsumoto_outdoor')) {
    return 'demo_comp_matsumoto'
  }
  if (id === 'demo_comp_shanye' || url.includes('demo_shanye_gear')) {
    return 'demo_comp_shanye'
  }
  return null
}

export function buildDemoSnapshots(competitorId) {
  const builder = DEMO_SNAPSHOT_BUILDERS[competitorId]
  if (!builder) return []

  const now = new Date()
  return builder().map(({ daysAgo, products }) => {
    const date = dateOffset(daysAgo)
    const crawledAt = daysAgo === 0
      ? nowUtc8String()
      : `${date} 08:00:00`
    return {
      competitorId,
      date,
      crawledAt,
      productCount: products.length,
      products,
    }
  })
}

/** 为任意竞店生成 Demo 快照（绑定到该竞店 id） */
export function buildDemoSnapshotsForCompetitor(competitor) {
  const templateId = resolveDemoTemplateId(competitor) || 'demo_comp_matsumoto'
  return buildDemoSnapshots(templateId).map((snapshot) => ({
    ...snapshot,
    competitorId: competitor.id,
  }))
}

export const DEMO_COMPETITOR_IDS = DEMO_COMPETITORS.map((c) => c.id)
