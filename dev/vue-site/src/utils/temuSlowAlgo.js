import { SLOW_MOVING_THRESHOLDS } from '@/constants/temu'

function roundInt(n) {
  return Math.max(0, Math.floor(Number(n) || 0))
}

export function isOnlineListingStatus(status) {
  return String(status) === '300'
}

export function salesTotalsFromRow(row) {
  const today = roundInt(row.son_today_sales ?? row.sonTodaySales)
  const s7 = roundInt(row.son_sales_seven_days ?? row.sonSalesSevenDays)
  const s30 = roundInt(row.son_sales_thirty_days ?? row.sonSalesThirtyDays)
  const stock = roundInt(row.warehouse_available_stock ?? row.warehouseAvailableStock ?? row.officialStock)
  const joinDays = roundInt(row.join_site_time ?? row.joinSiteTime)
  return { today, s7, s30, stock, joinDays }
}

/** 滞销候选：在线 + 官方仓有库存 + 近 7 日（含今日）无销量 */
export function isSlowCandidateRow(row) {
  if (!isOnlineListingStatus(row.status ?? row.listingStatus)) return false
  const { today, s7, stock } = salesTotalsFromRow(row)
  if (stock <= 0) return false
  return s7 <= 0 && today <= 0
}

/**
 * 未动销天数估算（与 spec §4.4 一致）
 * - 近 7 日有销 → 0（非滞销）
 * - 近 30 日无销 → 按上架天数 15/30/45
 * - 近 7 日无销、30 日有销 → 15（动销放缓）
 */
export function estimateDaysWithoutSaleFromRow(row) {
  const { today, s7, s30, joinDays } = salesTotalsFromRow(row)
  if (s7 > 0 || today > 0) return 0

  if (s30 <= 0) {
    if (joinDays >= 45) return Math.max(joinDays, 45)
    if (joinDays >= 30) return joinDays
    if (joinDays >= 15) return joinDays
    return 15
  }
  return 15
}

export function buildSlowMovingFromRow(row) {
  if (!isSlowCandidateRow(row)) return null
  const daysWithoutSale = estimateDaysWithoutSaleFromRow(row)
  if (daysWithoutSale < 15) return null

  let tierIndex = 0
  if (daysWithoutSale >= 45) tierIndex = 2
  else if (daysWithoutSale >= 30) tierIndex = 1

  const tier = SLOW_MOVING_THRESHOLDS[tierIndex]
  return {
    ...tier,
    daysWithoutSale,
    severity: tierIndex + 1,
    alertTitle: tierIndex === 2 ? '严重滞销' : tierIndex === 1 ? '滞销预警' : '动销放缓',
  }
}
