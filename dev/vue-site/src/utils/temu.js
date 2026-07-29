import { RESTOCK_CONFIG, SLOW_MOVING_THRESHOLDS, LISTING_STATUS } from '@/constants/temu'
import { TEMU_PLATFORM_IDS } from '@/constants/temuOps'
import { buildSlowMovingFromRow, estimateDaysWithoutSaleFromRow } from '@/utils/temuSlowAlgo'

/** 计算单件利润与是否亏损 */
export function calcProfit(product) {
  const costPrice = Number(product.costPrice) || 0
  const platformFee = product.sellingPrice * product.platformFeeRate
  const unitProfit = product.sellingPrice - costPrice - platformFee - product.logisticsFee
  const profitRate = product.sellingPrice > 0 ? (unitProfit / product.sellingPrice) * 100 : 0
  const hasCost = costPrice > 0
  return {
    platformFee: round2(platformFee),
    unitProfit: round2(unitProfit),
    profitRate: round2(profitRate),
    isLoss: hasCost && unitProfit < 0,
    hasCost,
  }
}

export function normalizeSalesLast7Days(value) {
  if (Array.isArray(value)) {
    return value.map((item) => Number(item) || 0)
  }
  if (typeof value === 'string' && value.trim()) {
    try {
      const parsed = JSON.parse(value)
      if (Array.isArray(parsed)) {
        return parsed.map((item) => Number(item) || 0)
      }
    } catch {
      return []
    }
  }
  return []
}

/** 7 日日均销量：优先用 Temu 近 7 日总量 / 7，避免整数拆分误差 */
export function calcAvg7DayDaily(salesLast7Days, sales7Total) {
  const totalFromField = Number(sales7Total)
  if (Number.isFinite(totalFromField) && totalFromField >= 0 && sales7Total != null && sales7Total !== '') {
    return round1(totalFromField / 7)
  }
  const series = normalizeSalesLast7Days(salesLast7Days)
  if (!series.length) return 0
  const total = series.reduce((s, n) => s + n, 0)
  return round1(total / series.length)
}

/**
 * 当日 vs 7 日均值：ratio = today / avg7
 * avg7≈0 且今日有销 → 返回 null（前端展示「新动销」，禁止哨兵 999 → +99800%）
 */
export function calcSurgeRatio(dailySales, avg7DayDaily) {
  const today = Number(dailySales) || 0
  const avg = Number(avg7DayDaily) || 0
  if (avg <= 0) return today > 0 ? null : 0
  return round2(today / avg)
}

/** 是否判定为爆款：增幅达标或「新动销」 */
export function isHotProduct(dailySales, avg7DayDaily, config = RESTOCK_CONFIG) {
  const today = Number(dailySales) || 0
  const avg = Number(avg7DayDaily) || 0
  if (today < config.hotMinDailySales) return false
  if (avg <= 0) return today >= config.hotMinDailySales
  return today / avg >= config.hotSurgeRatio
}

/** 滞销分级 */
export function getSlowMovingTiers(daysWithoutSale) {
  if (daysWithoutSale >= 45) {
    return { ...SLOW_MOVING_THRESHOLDS[2], daysWithoutSale, severity: 3, alertTitle: '严重滞销' }
  }
  if (daysWithoutSale >= 30) {
    return { ...SLOW_MOVING_THRESHOLDS[1], daysWithoutSale, severity: 2, alertTitle: '滞销预警' }
  }
  if (daysWithoutSale >= 15) {
    return { ...SLOW_MOVING_THRESHOLDS[0], daysWithoutSale, severity: 1, alertTitle: '动销放缓' }
  }
  return null
}

/** 官方仓可售天数 */
export function calcCoverDays(officialStock, dailyDemand) {
  if (dailyDemand <= 0) return officialStock > 0 ? 999 : 0
  return round1(officialStock / dailyDemand)
}

/**
 * 备货建议：本地仓 → Temu 官方仓
 * 目标库存 = 日均需求 × (目标覆盖天数 + 备货提前期)
 * 建议补货 = max(0, 目标库存 - 官方仓现有)；本地仓为 0 时仍展示需求量（shortfall）
 */
export function calcRestockPlan(product, config = RESTOCK_CONFIG) {
  const avg7DayDaily = calcAvg7DayDaily(product.salesLast7Days, product.sales7Total)
  const dailyDemand = Math.max(product.dailySales, avg7DayDaily)
  const targetStock = Math.ceil(dailyDemand * (config.targetCoverDays + config.leadTimeDays))
  const rawSuggest = Math.max(0, targetStock - product.officialStock)
  const localStock = product.localStock
  const hasLocalStock = localStock != null && localStock !== '' && Number(localStock) > 0
  const suggestedRestock = hasLocalStock
    ? Math.min(rawSuggest, Number(localStock))
    : rawSuggest
  const coverDays = calcCoverDays(product.officialStock, dailyDemand)
  const safetyStock = Math.ceil(dailyDemand * config.safetyDays)
  const stockGap = product.officialStock - safetyStock

  let urgency = 'normal'
  let urgencyLabel = '正常'
  if (coverDays <= config.leadTimeDays) {
    urgency = 'critical'
    urgencyLabel = '紧急补货'
  } else if (coverDays <= config.safetyDays) {
    urgency = 'warning'
    urgencyLabel = '建议补货'
  } else if (stockGap < 0) {
    urgency = 'caution'
    urgencyLabel = '低于安全线'
  }

  const isHot = isHotProduct(product.dailySales, avg7DayDaily, config)

  return {
    avg7DayDaily,
    dailyDemand: round1(dailyDemand),
    targetStock,
    suggestedRestock,
    coverDays,
    safetyStock,
    stockGap,
    urgency,
    urgencyLabel,
    isHot,
    canFulfill: hasLocalStock ? Number(localStock) >= rawSuggest : null,
    shortfall: hasLocalStock ? Math.max(0, rawSuggest - Number(localStock)) : rawSuggest,
    localStockKnown: hasLocalStock,
  }
}

/**  enrich 单条 SKU */
export function enrichTemuProduct(raw) {
  const profit = calcProfit(raw)
  const salesLast7Days = normalizeSalesLast7Days(raw.salesLast7Days)
  const sales7Total = Number.isFinite(Number(raw.sales7Total))
    ? Math.max(0, Math.floor(Number(raw.sales7Total)))
    : salesLast7Days.reduce((s, n) => s + n, 0)
  const avg7DayDaily = calcAvg7DayDaily(salesLast7Days, sales7Total)
  const surgeRatio = calcSurgeRatio(raw.dailySales, avg7DayDaily)
  const slowRow = {
    status: raw.listingStatus === 'offline' ? '400' : '300',
    son_today_sales: raw.dailySales,
    son_sales_seven_days: sales7Total,
    son_sales_thirty_days: raw.sales30Total ?? 0,
    warehouse_available_stock: raw.officialStock,
    join_site_time: raw.joinSiteTime ?? 0,
  }
  const slowMoving = buildSlowMovingFromRow(slowRow)
  const daysWithoutSale = slowMoving?.daysWithoutSale ?? estimateDaysWithoutSaleFromRow(slowRow)
  const restock = calcRestockPlan({ ...raw, salesLast7Days, sales7Total })
  const hot = isHotProduct(raw.dailySales, avg7DayDaily)
  const listingStatus = raw.listingStatus === 'offline' ? 'offline' : 'online'
  const listingMeta = LISTING_STATUS[listingStatus]
  const platformIds = raw.spuId
    ? { spuId: raw.spuId, skcId: raw.skcId || '', skuId: raw.skuId || '' }
    : (TEMU_PLATFORM_IDS[raw.sku] || {})

  return {
    ...raw,
    salesLast7Days,
    sales7Total,
    ...profit,
    ...platformIds,
    avg7DayDaily,
    surgeRatio,
    surgeIsNew: surgeRatio == null,
    slowMoving,
    daysWithoutSale,
    restock,
    isHot: hot,
    surgePercent: surgeRatio == null ? null : round1((surgeRatio - 1) * 100),
    listingStatus,
    isOnline: listingStatus === 'online',
    listingStatusLabel: listingMeta.label,
    listingStatusType: listingMeta.type,
  }
}

export function enrichAllProducts(rawList) {
  return rawList.map(enrichTemuProduct)
}

/** 增幅展示文案 */
export function formatSurgeDisplay(product) {
  if (product?.surgeIsNew || product?.surgeRatio == null) {
    return product?.dailySales > 0 ? '新动销' : '—'
  }
  const pct = Number(product.surgePercent)
  if (!Number.isFinite(pct)) return '—'
  const prefix = pct >= 0 ? '+' : ''
  return `${prefix}${pct.toFixed(1)}%`
}

function round1(n) {
  return Math.round(n * 10) / 10
}

function round2(n) {
  return Math.round(n * 100) / 100
}
